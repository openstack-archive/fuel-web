#    Copyright 2014 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os

from fuel_agent import errors
from fuel_agent import utils


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
    # Please take a look at the linux kernel documentation
    # https://github.com/torvalds/linux/blob/master/Documentation/devices.txt.
    # KVM virtio volumes have major number 252 in CentOS, but 253 in Ubuntu.
    valid_majors = (3, 8, 65, 66, 67, 68, 69, 70, 71,
                    104, 105, 106, 107, 108, 109, 110,
                    111, 202, 252, 253)
    if 'MAJOR' in uspec and int(uspec['MAJOR']) not in valid_majors:
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
        if key in ('MAJOR', 'MINOR', 'DEVNAME', 'DEVTYPE', 'DEVPATH',
                   'ID_BUS', 'ID_MODEL', 'ID_SERIAL_SHORT',
                   'ID_WWN', 'ID_CDROM'):
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
    if os.access('/sys/block/{0}/removable'.format(name), os.R_OK):
        with open('/sys/block/{0}/removable'.format(name)) as file:
            spec['removable'] = file.read().strip()

    for key in ('state', 'timeout'):
        if os.access('/sys/block/{0}/device/{1}'.format(name, key), os.R_OK):
            with open('/sys/block/{0}/device/{1}'.format(name, key)) as file:
                spec[key] = file.read().strip()
    return spec


def list():
    """Gets list of block devices, tries to guess which of them are disks
    and returns list of dicts representing those disks.

    :returns: A list of dict representing disks available on a node.
    """
    disks = []

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
        if not is_disk(device, bspec=bspec, uspec=uspec):
            continue

        disk = {
            'device': device,
            'startsec': line[startsec_idx],
            'size': utils.B2MiB(int(line[size_idx]), ceil=False),
            'uspec': uspec,
            'bspec': bspec,
            'espec': espec
        }
        disks.append(disk)
    return disks


def info(dev):
    result = utils.execute('parted', '-s', dev, '-m',
                           'unit', 'MiB',
                           'print', 'free',
                           check_exit_code=[0, 1])
    lines = result[0].split('\n')
    generic_params = lines[1].rstrip(';').split(':')
    generic = {
        'dev': generic_params[0],
        'size': utils.parse_unit(generic_params[1], 'MiB'),
        'logical_block': int(generic_params[3]),
        'physical_block': int(generic_params[4]),
        'table': generic_params[5],
        'model': generic_params[6]
    }
    parts = []
    for line in lines[2:]:
        line = line.strip().rstrip(';')
        if not line:
            continue
        part_params = line.split(':')
        parts.append({
            'num': int(part_params[0]),
            'begin': utils.parse_unit(part_params[1], 'MiB'),
            'end': utils.parse_unit(part_params[2], 'MiB'),
            'size': utils.parse_unit(part_params[3], 'MiB'),
            'fstype': part_params[4] or None
        })
    return {'generic': generic, 'parts': parts}


def wipe(dev):
    # making an empty new table is equivalent to wiping the old one
    make_label(dev)


def make_label(dev, label='gpt'):
    """Creates partition label on a device.

    :param dev: A device file, e.g. /dev/sda.
    :param label: Partition label type 'gpt' or 'msdos'. Optional.

    :returns: None
    """
    if label not in ('gpt', 'msdos'):
        raise errors.WrongPartitionLabelError(
            'Wrong partition label type: %s' % label)
    utils.execute('parted', '-s', dev, 'mklabel', label,
                  check_exit_code=[0])


def set_partition_flag(dev, num, flag, state='on'):
    """Sets flag on a partition

    :param dev: A device file, e.g. /dev/sda.
    :param num: Partition number
    :param flag: Flag name. Must be one of 'bios_grub', 'legacy_boot',
    'boot', 'raid', 'lvm'
    :param state: Desiable flag state. 'on' or 'off'. Default is 'on'.

    :returns: None
    """
    # parted supports more flags but we are interested in
    # setting only this subset of them.
    # not all of these flags are compatible with one another.
    if flag not in ('bios_grub', 'legacy_boot', 'boot', 'raid', 'lvm'):
        raise errors.WrongPartitionSchemeError(
            'Unsupported partition flag: %s' % flag)
    if state not in ('on', 'off'):
        raise errors.WrongPartitionSchemeError(
            'Wrong partition flag state: %s' % state)
    utils.execute('parted', '-s', dev, 'set', str(num),
                  flag, state, check_exit_code=[0])


def make_partition(dev, begin, end, ptype):
    if ptype not in ('primary', 'logical'):
        raise errors.WrongPartitionSchemeError(
            'Wrong partition type: %s' % ptype)

    # check begin >= end
    if begin >= end:
        raise errors.WrongPartitionSchemeError(
            'Wrong boundaries: begin >= end')

    # check if begin and end are inside one of free spaces available
    if not any(x['fstype'] == 'free' and begin >= x['begin'] and
               end <= x['end'] for x in info(dev)['parts']):
        raise errors.WrongPartitionSchemeError(
            'Invalid boundaries: begin and end '
            'are not inside available free space'
        )

    utils.execute('parted', '-a', 'optimal', '-s', dev, 'unit', 'MiB',
        'mkpart', ptype, str(begin), str(end), check_exit_code=[0])


def remove_partition(dev, num):
    if not any(x['fstype'] != 'free' and x['num'] == num
               for x in info(dev)['parts']):
        raise errors.PartitionNotFoundError('Partition %s not found' % num)
    utils.execute('parted', '-s', dev, 'rm', str(num), check_exit_code=[0])
