# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from fuel_agent.utils import utils


# Please take a look at the linux kernel documentation
# https://github.com/torvalds/linux/blob/master/Documentation/devices.txt.
# KVM virtio volumes have major number 252 in CentOS, but 253 in Ubuntu.
VALID_MAJORS = (3, 8, 65, 66, 67, 68, 69, 70, 71, 104, 105, 106, 107, 108, 109,
                110, 111, 202, 252, 253)

# We are only interested in getting these
# properties from udevadm report
# MAJOR major device number
# MINOR minor device number
# DEVNAME e.g. /dev/sda
# DEVTYPE e.g. disk or partition for block devices
# DEVPATH path to a device directory relative to /sys
# ID_BUS e.g. ata, scsi
# ID_MODEL e.g. MATSHITADVD-RAM_UJ890
# ID_SERIAL_SHORT e.g. UH00_296679
# ID_WWN e.g. 0x50000392e9804d4b (optional)
# ID_CDROM e.g. 1 for cdrom device (optional)
UDEV_PROPERTIES = set(['MAJOR', 'MINOR', 'DEVNAME', 'DEVTYPE', 'DEVPATH',
                       'ID_BUS', 'ID_MODEL', 'ID_SERIAL_SHORT', 'ID_WWN',
                       'ID_CDROM'])

# more details about types you can find in dmidecode's manual
SMBIOS_TYPES = {'bios': '0',
                'base_board': '2',
                'processor': '4',
                'memory_array': '16',
                'memory_device': '17'}


def parse_dmidecode(type):
    """Parses `dmidecode` output.

    :param type: A string with type of entity to display.

    :returns: A list with dictionaries of entities for specified type.
    """
    output = utils.execute('dmidecode', '-q', '--type', type)
    lines = output[0].split('\n')
    info = []
    multiline_values = None
    section = 0

    for line in lines:
        if len(line) != 0 and len(line.strip()) == len(line):
            info.append({})
            section = len(info) - 1
        try:
            k, v = (l.strip() for l in line.split(':', 1))
        except ValueError:
            k = line.strip()
            if not k:
                multiline_values = None
            if multiline_values:
                info[section][multiline_values].append(k)
        else:
            if not v:
                multiline_values = k.lower()
                info[section][multiline_values] = []
            else:
                info[section][k.lower()] = v

    return info


def parse_lspci():
    """Parses `lspci` output.

    :returns: A list of dicts containing PCI devices information
    """
    output = utils.execute('lspci', '-vmm', '-D')
    lines = output[0].split('\n')
    info = [{}]
    section = 0

    for line in lines[:-2]:
        try:
            k, v = (l.strip() for l in line.split(':', 1))
        except ValueError:
            info.append({})
            section += 1
        else:
            info[section][k.lower()] = v

    return info


def parse_simple_kv(*command):
    """Parses simple key:value output from specified command.

    :param command: A command to execute

    :returns: A dict of parsed key-value data
    """
    output = utils.execute(*command)
    lines = output[0].split('\n')
    info = {}

    for line in lines[:-1]:
        try:
            k, v = (l.strip() for l in line.split(':', 1))
        except ValueError:
            break
        else:
            info[k.lower()] = v

    return info


def is_disk(dev, bspec=None, uspec=None):
    """Checks if given device is a disk.

    :param dev: A device file, e.g. /dev/sda.
    :param bspec: A dict of properties which we get from blockdev.
    :param uspec: A dict of properties which we get from udevadm.

    :returns: True if device is disk else False.
    """

    # Filtering by udevspec
    if uspec is None:
        uspec = udevreport(dev)
    if uspec.get('ID_CDROM') == '1':
        return False
    if uspec.get('DEVTYPE') == 'partition':
        return False
    if 'MAJOR' in uspec and int(uspec['MAJOR']) not in VALID_MAJORS:
        return False

    # Filtering by blockdev spec
    if bspec is None:
        bspec = blockdevreport(dev)
    if bspec.get('ro') == '1':
        return False

    return True


def udevreport(dev):
    """Builds device udevadm report.

    :param dev: A device file, e.g. /dev/sda.

    :returns: A dict of udev device properties.
    """
    report = utils.execute('udevadm',
                           'info',
                           '--query=property',
                           '--export',
                           '--name={0}'.format(dev),
                           check_exit_code=[0])[0]

    spec = {}
    for line in [l for l in report.splitlines() if l]:
        key, value = line.split('=', 1)
        value = value.strip('\'')

        # This is a list of symbolic links which were created for this
        # block device (e.g. /dev/disk/by-id/foobar)
        if key == 'DEVLINKS':
            spec['DEVLINKS'] = value.split()

        if key in UDEV_PROPERTIES:
            spec[key] = value
    return spec


def blockdevreport(blockdev):
    """Builds device blockdev report.

    :param blockdev: A block device file, e.g. /dev/sda.

    :returns: A dict of blockdev properties.
    """
    cmd = [
        'blockdev',
        '--getsz',        # get size in 512-byte sectors
        '--getro',        # get read-only
        '--getss',        # get logical block (sector) size
        '--getpbsz',      # get physical block (sector) size
        '--getsize64',    # get size in bytes
        '--getiomin',     # get minimum I/O size
        '--getioopt',     # get optimal I/O size
        '--getra',        # get readahead
        '--getalignoff',  # get alignment offset in bytes
        '--getmaxsect',   # get max sectors per request
        blockdev
    ]
    opts = [o[5:] for o in cmd if o.startswith('--get')]
    report = utils.execute(*cmd, check_exit_code=[0])[0]
    return dict(zip(opts, report.splitlines()))


def extrareport(dev):
    """Builds device report using some additional sources.

    :param dev: A device file, e.g. /dev/sda.

    :returns: A dict of properties.
    """
    spec = {}
    name = os.path.basename(dev)

    # Finding out if block device is removable or not
    # actually, some disks are marked as removable
    # while they are actually not e.g. Adaptec RAID volumes
    try:
        with open('/sys/block/{0}/removable'.format(name)) as file:
            spec['removable'] = file.read().strip()
    except Exception:
        pass

    for key in ('state', 'timeout'):
        try:
            with open('/sys/block/{0}/device/{1}'.format(name, key)) as file:
                spec[key] = file.read().strip()
        except Exception:
            pass

    return spec


def list_block_devices(disks=True):
    """Gets list of block devices, tries to guess which of them are disks
    and returns list of dicts representing those disks.

    :returns: A list of dict representing disks available on a node.
    """
    bdevs = []

    report = utils.execute('blockdev', '--report', check_exit_code=[0])[0]
    lines = [line.split() for line in report.splitlines() if line]

    startsec_idx = lines[0].index('StartSec')
    device_idx = lines[0].index('Device')
    size_idx = lines[0].index('Size')

    for line in lines[1:]:
        device = line[device_idx]
        uspec = udevreport(device)
        bspec = blockdevreport(device)
        espec = extrareport(device)

        # if device is not disk,skip it
        if disks and not is_disk(device, bspec=bspec, uspec=uspec):
            continue

        bdev = {
            'device': device,
            'startsec': line[startsec_idx],
            'size': int(line[size_idx]),
            'uspec': uspec,
            'bspec': bspec,
            'espec': espec
        }
        bdevs.append(bdev)
    return bdevs


def match_device(uspec1, uspec2):
    """Tries to find out if uspec1 and uspec2 are uspecs from the same device.
    It compares only some fields in uspecs (not all of them) which, we believe,
    is enough to say exactly whether uspecs belong to the same device or not.

    :param uspec1: A dict of properties which we get from udevadm.
    :param uspec1: A dict of properties which we get from udevadm.

    :returns: True if uspecs match each other else False.
    """

    # False if ID_WWN is given and does not match each other
    if ('ID_WWN' in uspec1 and 'ID_WWN' in uspec2
            and uspec1['ID_WWN'] != uspec2['ID_WWN']):
        return False

    # False if ID_SERIAL_SHORT is given and does not match each other
    if ('ID_SERIAL_SHORT' in uspec1 and 'ID_SERIAL_SHORT' in uspec2
            and uspec1['ID_SERIAL_SHORT'] != uspec2['ID_SERIAL_SHORT']):
        return False

    # True if at least one by-id link is the same for both uspecs
    if ('DEVLINKS' in uspec1 and 'DEVLINKS' in uspec2
            and any(x.startswith('/dev/disk/by-id') for x in
                    set(uspec1['DEVLINKS']) & set(uspec2['DEVLINKS']))):
        return True

    # True if ID_WWN is given and matches each other
    # and DEVTYPE is given and is 'disk'
    if (uspec1.get('ID_WWN') == uspec2.get('ID_WWN') is not None
            and uspec1.get('DEVTYPE') == uspec2.get('DEVTYPE') == 'disk'):
        return True

    # True if ID_WWN is given and matches each other
    # and DEVTYPE is given and is 'partition'
    # and MINOR is given and matches each other
    if (uspec1.get('ID_WWN') == uspec2.get('ID_WWN') is not None
            and uspec1.get('DEVTYPE') == uspec2.get('DEVTYPE') == 'partition'
            and uspec1.get('MINOR') == uspec2.get('MINOR') is not None):
        return True

    # True if ID_SERIAL_SHORT is given and matches each other
    # and DEVTYPE is given and is 'disk'
    if (uspec1.get('ID_SERIAL_SHORT') == uspec2.get('ID_SERIAL_SHORT')
            is not None
            and uspec1.get('DEVTYPE') == uspec2.get('DEVTYPE') == 'disk'):
        return True

    # True if DEVPATH is given and matches each other
    if uspec1.get('DEVPATH') == uspec2.get('DEVPATH') is not None:
        return True

    return False
