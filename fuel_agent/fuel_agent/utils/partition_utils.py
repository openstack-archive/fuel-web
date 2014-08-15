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

from fuel_agent import errors
from fuel_agent.utils import utils


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
    output = utils.execute('parted -s %s -m unit MiB print free' % dev,
                           check_exit_code=[0, 1])[0]
    return parse_partition_info(output)


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
    utils.execute('parted -s %s mklabel %s' % (dev, label),
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
    utils.execute('parted -s %s set %s %s %s' % (dev, str(num), flag, state),
                  check_exit_code=[0])


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
    utils.execute('sgdisk --typecode=%s:%s %s' % (num, type_guid, dev),
                  check_exit_code=[0])


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

    utils.execute('parted -a optimal -s %s unit MiB mkpart %s %s %s' %
                  (dev, ptype, str(begin), str(end)),
                  check_exit_code=[0])


def remove_partition(dev, num):
    if not any(x['fstype'] != 'free' and x['num'] == num
               for x in info(dev)['parts']):
        raise errors.PartitionNotFoundError('Partition %s not found' % num)
    utils.execute('parted -s %s rm %s' % (dev, str(num)), check_exit_code=[0])
