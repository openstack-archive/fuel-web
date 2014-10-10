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

import time

from fuel_agent import errors
from fuel_agent.openstack.common import log as logging
from fuel_agent.utils import utils

LOG = logging.getLogger(__name__)


def parse_partition_info(output):
    lines = output.split('\n')
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


def info(dev):
    output = utils.execute('parted', '-s', dev, '-m',
                           'unit', 'MiB',
                           'print', 'free',
                           check_exit_code=[0, 1])[0]
    LOG.debug('Info output: \n%s' % output)
    result = parse_partition_info(output)
    LOG.debug('Info result: %s' % result)
    return result


def wipe(dev):
    # making an empty new table is equivalent to wiping the old one
    LOG.debug('Wiping partition table on %s (we assume it is equal '
              'to creating a new one)' % dev)
    make_label(dev)


def make_label(dev, label='gpt'):
    """Creates partition label on a device.

    :param dev: A device file, e.g. /dev/sda.
    :param label: Partition label type 'gpt' or 'msdos'. Optional.

    :returns: None
    """
    LOG.debug('Trying to create %s partition table on device %s' %
              (label, dev))
    if label not in ('gpt', 'msdos'):
        raise errors.WrongPartitionLabelError(
            'Wrong partition label type: %s' % label)
    out, err = utils.execute('parted', '-s', dev, 'mklabel', label,
                             check_exit_code=[0, 1])
    LOG.debug('Parted output: \n%s' % out)
    reread_partitions(dev, out=out)


def set_partition_flag(dev, num, flag, state='on'):
    """Sets flag on a partition

    :param dev: A device file, e.g. /dev/sda.
    :param num: Partition number
    :param flag: Flag name. Must be one of 'bios_grub', 'legacy_boot',
    'boot', 'raid', 'lvm'
    :param state: Desiable flag state. 'on' or 'off'. Default is 'on'.

    :returns: None
    """
    LOG.debug('Trying to set partition flag: dev=%s num=%s flag=%s state=%s' %
              (dev, num, flag, state))
    # parted supports more flags but we are interested in
    # setting only this subset of them.
    # not all of these flags are compatible with one another.
    if flag not in ('bios_grub', 'legacy_boot', 'boot', 'raid', 'lvm'):
        raise errors.WrongPartitionSchemeError(
            'Unsupported partition flag: %s' % flag)
    if state not in ('on', 'off'):
        raise errors.WrongPartitionSchemeError(
            'Wrong partition flag state: %s' % state)
    out, err = utils.execute('parted', '-s', dev, 'set', str(num),
                             flag, state, check_exit_code=[0, 1])
    LOG.debug('Parted output: \n%s' % out)
    reread_partitions(dev, out=out)


def set_gpt_type(dev, num, type_guid):
    """Sets guid on a partition.

    :param dev: A device file, e.g. /dev/sda.
    :param num: Partition number
    :param type_guid: Partition type guid. Must be one of those listed
    on this page http://en.wikipedia.org/wiki/GUID_Partition_Table.
    This method does not check whether type_guid is valid or not.

    :returns: None
    """
    # TODO(kozhukalov): check whether type_guid is valid
    LOG.debug('Setting partition GUID: dev=%s num=%s guid=%s' %
              (dev, num, type_guid))
    utils.execute('sgdisk', '--typecode=%s:%s' % (num, type_guid),
                  dev, check_exit_code=[0])


def make_partition(dev, begin, end, ptype):
    LOG.debug('Trying to create a partition: dev=%s begin=%s end=%s' %
              (dev, begin, end))
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
            'are not inside available free space')

    out, err = utils.execute(
        'parted', '-a', 'optimal', '-s', dev, 'unit', 'MiB',
        'mkpart', ptype, str(begin), str(end), check_exit_code=[0, 1])
    LOG.debug('Parted output: \n%s' % out)
    reread_partitions(dev, out=out)


def remove_partition(dev, num):
    LOG.debug('Trying to remove partition: dev=%s num=%s' % (dev, num))
    if not any(x['fstype'] != 'free' and x['num'] == num
               for x in info(dev)['parts']):
        raise errors.PartitionNotFoundError('Partition %s not found' % num)
    out, err = utils.execute('parted', '-s', dev, 'rm',
                             str(num), check_exit_code=[0])
    reread_partitions(dev, out=out)


def reread_partitions(dev, out='Device or resource busy', timeout=30):
    # The reason for this method to exist is that old versions of parted
    # use ioctl(fd, BLKRRPART, NULL) to tell Linux to re-read partitions.
    # This system call does not work sometimes. So we try to re-read partition
    # table several times. Besides partprobe uses BLKPG instead, which
    # is better than BLKRRPART for this case. BLKRRPART tells Linux to re-read
    # partitions while BLKPG tells Linux which partitions are available
    # BLKPG is usually used as a fallback system call.
    begin = time.time()
    while 'Device or resource busy' in out:
        if time.time() > begin + timeout:
            raise errors.BaseError('Unable to re-read partition table on'
                                   'device %s' % dev)
        LOG.debug('Last time output contained "Device or resource busy". '
                  'Trying to re-read partition table on device %s' % dev)
        out, err = utils.execute('partprobe', dev, check_exit_code=[0, 1])
        LOG.debug('Partprobe output: \n%s' % out)
        pout, perr = utils.execute('partx', '-a', dev, check_exit_code=[0, 1])
        LOG.debug('Partx output: \n%s' % pout)
        time.sleep(1)
