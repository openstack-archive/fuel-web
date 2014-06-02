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


import mock
import os
from oslotest import base as test_base
import six.moves.builtins as __builtin__

from ironic_python_agent import disk_utils as du
from ironic_python_agent import errors
from ironic_python_agent import utils


class DiskUtilsTestCase(test_base.BaseTestCase):
    @mock.patch.object(utils, 'execute')
    def test_info(self, mock_exec):
        # should run parted OS command
        # in order to get drive info (table, size, partitions, free space)
        mock_exec.return_value = (
            'BYT;\n'
            '/dev/fake:100000MiB:scsi:512:4096:msdos:DRIVE MODEL:;\n'
            '1:0.03MiB:1.00MiB:0.97MiB:free;\n'
            '1:1.00MiB:8001MiB:8000MiB:linux-swap(v1)::;\n'
            '2:8001MiB:20001MiB:12000MiB:ext4::boot;\n'
            '3:20001MiB:80001MiB:60000MiB:ext4::;\n'
            '1:80001MiB:100000MiB:19999MiB:free;\n',
            ''
        )
        expected = {
            'generic': {
                'dev': '/dev/fake',
                'table': 'msdos',
                'size': 100000,
                'model': 'DRIVE MODEL',
                'logical_block': 512,
                'physical_block': 4096
            },
            'parts': [
                {
                    'begin': 1,
                    'end': 1,
                    'size': 1,
                    'num': 1,
                    'fstype': 'free'
                },
                {
                    'begin': 1,
                    'end': 8001,
                    'size': 8000,
                    'num': 1,
                    'fstype': 'linux-swap(v1)'
                },
                {
                    'begin': 8001,
                    'end': 20001,
                    'size': 12000,
                    'num': 2,
                    'fstype': 'ext4'
                },
                {
                    'begin': 20001,
                    'end': 80001,
                    'size': 60000,
                    'num': 3,
                    'fstype': 'ext4'
                },
                {
                    'begin': 80001,
                    'end': 100000,
                    'size': 19999,
                    'num': 1,
                    'fstype': 'free'
                }
            ]
        }
        info = du.info('/dev/fake')
        mock_exec.assert_called_once_with('parted', '-s', '/dev/fake', '-m',
            'unit', 'MiB', 'print', 'free', check_exit_code=[0, 1])
        self.assertEqual(expected, info)

    @mock.patch.object(du, 'make_label')
    def test_wipe(self, mock_label):
        # should run call make_label method
        # in order to create new empty table which we think
        # is equivalent to wiping the old one
        du.wipe('/dev/fake')
        mock_label.assert_called_once_with('/dev/fake')

    @mock.patch.object(utils, 'execute')
    def test_make_label(self, mock_exec):
        # should run parted OS command
        # in order to create label on a device

        # gpt by default
        du.make_label('/dev/fake')
        mock_exec.assert_called_once_with('parted', '-s', '/dev/fake',
            'mklabel', 'gpt', check_exit_code=[0])
        mock_exec.reset_mock()

        # label is set explicitly
        du.make_label('/dev/fake', label='msdos')
        mock_exec.assert_called_once_with('parted', '-s', '/dev/fake',
            'mklabel', 'msdos', check_exit_code=[0])

    def test_make_label_wrong_label(self):
        # should check if label is valid
        # should raise exception if it is not
        self.assertRaises(errors.WrongPartitionLabelError,
                          du.make_label, '/dev/fake', 'wrong')

    @mock.patch.object(utils, 'execute')
    def test_set_partition_flag(self, mock_exec):
        # should run parted OS command
        # in order to set flag on a partition

        # default state is 'on'
        du.set_partition_flag('/dev/fake', 1, 'boot')
        mock_exec.assert_called_once_with(
            'parted', '-s', '/dev/fake', 'set', '1', 'boot', 'on',
            check_exit_code=[0])
        mock_exec.reset_mock()

        # if state argument is given use it
        du.set_partition_flag('/dev/fake', 1, 'boot', state='off')
        mock_exec.assert_called_once_with(
            'parted', '-s', '/dev/fake', 'set', '1', 'boot', 'off',
            check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_set_partition_flag_wrong_flag(self, mock_exec):
        # should check if flag is valid
        # should raise exception if it is not
        self.assertRaises(errors.WrongPartitionSchemeError,
                          du.set_partition_flag,
                          '/dev/fake', 1, 'wrong')

    @mock.patch.object(utils, 'execute')
    def test_set_partition_flag_wrong_state(self, mock_exec):
        # should check if flag is valid
        # should raise exception if it is not
        self.assertRaises(errors.WrongPartitionSchemeError,
                          du.set_partition_flag,
                          '/dev/fake', 1, 'boot', state='wrong')

    @mock.patch.object(du, 'info')
    @mock.patch.object(utils, 'execute')
    def test_make_partition(self, mock_exec, mock_info):
        # should run parted OS command
        # in order to create new partition
        mock_info.return_value = {
            'parts': [
                {'begin': 0, 'end': 1000, 'fstype': 'free'},
            ]
        }
        du.make_partition('/dev/fake', 100, 200, 'primary')
        mock_exec.assert_called_once_with(
            'parted',
            '-a', 'optimal',
            '-s', '/dev/fake',
            'unit', 'MiB',
            'mkpart', 'primary', '100', '200',
            check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_make_partition_wrong_ptype(self, mock_exec):
        # should check if partition type is one of
        # 'primary' or 'logical'
        # should raise exception if it is not
        self.assertRaises(errors.WrongPartitionSchemeError, du.make_partition,
                          '/dev/fake', 200, 100, 'wrong')

    @mock.patch.object(utils, 'execute')
    def test_make_partition_begin_overlaps_end(self, mock_exec):
        # should check if begin is less than end
        # should raise exception if it isn't
        self.assertRaises(errors.WrongPartitionSchemeError, du.make_partition,
                          '/dev/fake', 200, 100, 'primary')

    @mock.patch.object(du, 'info')
    @mock.patch.object(utils, 'execute')
    def test_make_partition_overlaps_other_parts(self, mock_exec, mock_info):
        # should check if begin or end overlap other partitions
        # should raise exception if it does
        mock_info.return_value = {
            'parts': [
                {'begin': 0, 'end': 100, 'fstype': 'free'},
                {'begin': 100, 'end': 200, 'fstype': 'notfree'},
                {'begin': 200, 'end': 300, 'fstype': 'free'}
            ]
        }
        self.assertRaises(errors.WrongPartitionSchemeError, du.make_partition,
            '/dev/fake', 99, 101, 'primary')
        self.assertRaises(errors.WrongPartitionSchemeError, du.make_partition,
            '/dev/fake', 100, 200, 'primary')
        self.assertRaises(errors.WrongPartitionSchemeError, du.make_partition,
            '/dev/fake', 200, 301, 'primary')
        self.assertEqual(mock_info.call_args_list,
                         [mock.call('/dev/fake')] * 3)

    @mock.patch.object(du, 'info')
    @mock.patch.object(utils, 'execute')
    def test_remove_partition(self, mock_exec, mock_info):
        # should run parted OS command
        # in order to remove partition
        mock_info.return_value = {
            'parts': [
                {
                    'begin': 1,
                    'end': 100,
                    'size': 100,
                    'num': 1,
                    'fstype': 'ext2'
                },
                {
                    'begin': 100,
                    'end': 200,
                    'size': 100,
                    'num': 2,
                    'fstype': 'ext2'
                }
            ]
        }
        du.remove_partition('/dev/fake', 1)
        mock_exec.assert_called_once_with(
            'parted', '-s', '/dev/fake', 'rm', '1',
            check_exit_code=[0])

    @mock.patch.object(du, 'info')
    @mock.patch.object(utils, 'execute')
    def test_remove_partition_notexists(self, mock_exec, mock_info):
        # should check if partition does exist
        # should raise exception if it doesn't
        mock_info.return_value = {
            'parts': [
                {
                    'begin': 1,
                    'end': 100,
                    'size': 100,
                    'num': 1,
                    'fstype': 'ext2'
                },
                {
                    'begin': 100,
                    'end': 200,
                    'size': 100,
                    'num': 2,
                    'fstype': 'ext2'
                }
            ]
        }
        self.assertRaises(errors.PartitionNotFoundError, du.remove_partition,
            '/dev/fake', 3)

    @mock.patch.object(utils, 'execute')
    def test_udevreport(self, mock_exec):
        # should run udevadm info OS command
        # in order to get udev properties for a device
        mock_exec.return_value = (
            'DEVLINKS=\'/dev/disk/by-id/fakeid1 /dev/disk/by-id/fakeid2\'\n'
            'DEVNAME=\'/dev/fake\'\n'
            'DEVPATH=\'/devices/fakepath\'\n'
            'DEVTYPE=\'disk\'\n'
            'MAJOR=\'11\'\n'
            'MINOR=\'0\'\n'
            'ID_BUS=\'fakebus\'\n'
            'ID_MODEL=\'fakemodel\'\n'
            'ID_SERIAL_SHORT=\'fakeserial\'\n'
            'ID_WWN=\'fakewwn\'\n'
            'ID_CDROM=\'1\'\n'
            'ANOTHER=\'another\'\n',
            ''
        )
        expected = {
            'DEVLINKS': ['/dev/disk/by-id/fakeid1', '/dev/disk/by-id/fakeid2'],
            'DEVNAME': '/dev/fake',
            'DEVPATH': '/devices/fakepath',
            'DEVTYPE': 'disk',
            'MAJOR': '11',
            'MINOR': '0',
            'ID_BUS': 'fakebus',
            'ID_MODEL': 'fakemodel',
            'ID_SERIAL_SHORT': 'fakeserial',
            'ID_WWN': 'fakewwn',
            'ID_CDROM': '1'
        }
        self.assertEqual(expected, du.udevreport('/dev/fake'))
        mock_exec.assert_called_once_with('udevadm',
                                          'info',
                                          '--query=property',
                                          '--export',
                                          '--name=/dev/fake',
                                          check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_blockdevreport(self, mock_exec):
        # should run blockdev OS command
        # in order to get block device properties
        cmd = ['blockdev', '--getsz', '--getro', '--getss', '--getpbsz',
               '--getsize64', '--getiomin', '--getioopt', '--getra',
               '--getalignoff', '--getmaxsect', '/dev/fake']
        mock_exec.return_value = (
            '625142448\n0\n512\n4096\n320072933376\n4096\n0\n256\n0\n1024',
            ''
        )
        expected = {
            'sz': '625142448',
            'ro': '0',
            'ss': '512',
            'pbsz': '4096',
            'size64': '320072933376',
            'iomin': '4096',
            'ioopt': '0',
            'ra': '256',
            'alignoff': '0',
            'maxsect': '1024'
        }
        self.assertEqual(expected, du.blockdevreport('/dev/fake'))
        mock_exec.assert_called_once_with(*cmd, check_exit_code=[0])

    @mock.patch.object(os, 'access')
    def test_extrareport(self, mock_access):
        # should read some files from sysfs e.g. /sys/block/fake/removable
        # in order to get some device properties
        with mock.patch.object(__builtin__, 'open') as mock_open:
            def with_side_effect(arg):
                mock_with = mock.MagicMock()
                mock_with.__exit__.return_value = None
                mock_file = mock.Mock()
                if arg == '/sys/block/fake/removable':
                    mock_file.read.return_value = '0\n'
                elif arg == '/sys/block/fake/device/state':
                    mock_file.read.return_value = 'running\n'
                elif arg == '/sys/block/fake/device/timeout':
                    mock_file.read.return_value = '30\n'
                mock_with.__enter__.return_value = mock_file
                return mock_with
            mock_open.side_effect = with_side_effect
            expected = {'removable': '0', 'state': 'running', 'timeout': '30'}
            mock_access.return_value = True
            self.assertEqual(expected, du.extrareport('/dev/fake'))
            mock_access.reset_mock()
            mock_access.return_value = False
            self.assertEqual({}, du.extrareport('/dev/fake'))

    @mock.patch.object(du, 'blockdevreport')
    @mock.patch.object(du, 'udevreport')
    def test_is_disk_uspec_bspec_none(self, mock_ureport, mock_breport):
        # should call udevreport if uspec is None
        # should call blockdevreport if bspec is None
        # should return True if uspec and bspec are empty
        mock_ureport.return_value = {}
        mock_breport.return_value = {}
        self.assertTrue(du.is_disk('/dev/fake'))
        mock_ureport.assert_called_once_with('/dev/fake')
        mock_breport.assert_called_once_with('/dev/fake')

    @mock.patch.object(du, 'udevreport')
    def test_is_disk_uspec_none(self, mock_ureport):
        # should call udevreport if uspec is None but bspec is not None
        bspec = {'key': 'value'}
        mock_ureport.return_value = {}
        du.is_disk('/dev/fake', bspec=bspec)
        mock_ureport.assert_called_once_with('/dev/fake')

    @mock.patch.object(du, 'blockdevreport')
    def test_is_disk_bspec_none(self, mock_breport):
        # should call blockdevreport if bspec is None but uspec is not None
        uspec = {'key': 'value'}
        mock_breport.return_value = {}
        du.is_disk('/dev/fake', uspec=uspec)
        mock_breport.assert_called_once_with('/dev/fake')

    @mock.patch.object(du, 'blockdevreport')
    def test_is_disk_cdrom(self, mock_breport):
        # should return False if udev ID_CDROM is set to 1
        mock_breport.return_value = {}
        uspec = {
            'ID_CDROM': '1'
        }
        self.assertFalse(du.is_disk('/dev/fake', uspec=uspec))

    @mock.patch.object(du, 'blockdevreport')
    def test_is_disk_partition(self, mock_breport):
        # should return False if udev DEVTYPE is partition
        mock_breport.return_value = {}
        uspec = {
            'DEVTYPE': 'partition'
        }
        self.assertFalse(du.is_disk('/dev/fake', uspec=uspec))

    @mock.patch.object(du, 'blockdevreport')
    def test_is_disk_major(self, mock_breport):
        # should return False if udev MAJOR is not in a list of
        # major numbers which are used for disks
        # look at kernel/Documentation/devices.txt
        mock_breport.return_value = {}
        valid_majors = [3, 8, 65, 66, 67, 68, 69, 70, 71, 104, 105,
                        106, 107, 108, 109, 110, 111, 202, 252, 253]
        for major in (set(range(1, 261)) - set(valid_majors)):
            uspec = {
                'MAJOR': str(major)
            }
            self.assertFalse(du.is_disk('/dev/fake', uspec=uspec))

    @mock.patch.object(du, 'udevreport')
    def test_is_disk_readonly(self, mock_ureport):
        # should return False if device is read only
        mock_ureport.return_value = {}
        bspec = {
            'ro': '1'
        }
        self.assertFalse(du.is_disk('/dev/fake', bspec=bspec))

    @mock.patch.object(du, 'is_disk')
    @mock.patch.object(du, 'extrareport')
    @mock.patch.object(du, 'blockdevreport')
    @mock.patch.object(du, 'udevreport')
    @mock.patch.object(utils, 'execute')
    def test_list(self, mock_exec, mock_ureport, mock_breport,
                  mock_ereport, mock_isdisk):
        # should run blockdev --report command
        # in order to get a list of block devices
        # should call report methods to get device info
        # should call is_disk method to filter out
        # those block devices which are not disks
        mock_exec.return_value = (
            'RO    RA   SSZ   BSZ   StartSec            Size   Device\n'
            'rw   256   512  4096          0    320072933376   /dev/fake\n'
            'rw   256   512  4096       2048      7998537728   /dev/fake1\n'
            'rw   256   512   512          0      1073741312   /dev/sr0\n',
            ''
        )

        def isdisk_side_effect(arg, uspec=None, bspec=None):
            if arg == '/dev/fake':
                return True
            elif arg in ('/dev/fake1', '/dev/sr0'):
                return False
        mock_isdisk.side_effect = isdisk_side_effect
        mock_ureport.return_value = {'key0': 'value0'}
        mock_breport.return_value = {'key1': 'value1'}
        mock_ereport.return_value = {'key2': 'value2'}

        expected = [{
            'device': '/dev/fake',
            'startsec': '0',
            'size': 305245,
            'uspec': {'key0': 'value0'},
            'bspec': {'key1': 'value1'},
            'espec': {'key2': 'value2'}
        }]
        self.assertEqual(du.list(), expected)
        mock_exec.assert_called_once_with('blockdev', '--report',
                                          check_exit_code=[0])
        self.assertEqual(mock_ureport.call_args_list, [mock.call('/dev/fake'),
            mock.call('/dev/fake1'), mock.call('/dev/sr0')])
        self.assertEqual(mock_breport.call_args_list, [mock.call('/dev/fake'),
            mock.call('/dev/fake1'), mock.call('/dev/sr0')])
        self.assertEqual(mock_ereport.call_args_list, [mock.call('/dev/fake'),
            mock.call('/dev/fake1'), mock.call('/dev/sr0')])

    def test_match_device_devlinks(self):
        # should return true if at least one by-id link from first uspec
        # matches by-id link from another uspec
        uspec1 = {'DEVLINKS': ['/dev/disk/by-path/fakepath',
                               '/dev/disk/by-id/fakeid1',
                               '/dev/disk/by-id/fakeid2']}
        uspec2 = {'DEVLINKS': ['/dev/disk/by-id/fakeid2',
                               '/dev/disk/by-id/fakeid3']}
        self.assertTrue(du.match_device(uspec1, uspec2))

    def test_match_device_wwn(self):
        # should return true if ID_WWN is given
        # and if it is the same in both uspecs
        # and if DEVTYPE is given and if DEVTYPE is disk
        # or if DEVTYPE is partition and MINOR is the same for both uspecs
        uspec1 = uspec2 = {'ID_WWN': 'fakewwn',
                           'DEVTYPE': 'disk'}
        self.assertTrue(du.match_device(uspec1, uspec2))
        uspec1 = uspec2 = {'ID_WWN': 'fakewwn',
                           'DEVTYPE': 'partition',
                           'MINOR': '1'}
        self.assertTrue(du.match_device(uspec1, uspec2))

    def test_match_device_wwn_false(self):
        # should return false if ID_WWN is given
        # and does not match each other
        uspec1 = {'ID_WWN': 'fakewwn1'}
        uspec2 = {'ID_WWN': 'fakewwn2'}
        self.assertFalse(du.match_device(uspec1, uspec2))

    def test_match_device_devpath(self):
        # should return true if DEVPATH is given
        # and if it is the same for both uspecs
        uspec1 = uspec2 = {'DEVPATH': '/devices/fake'}
        self.assertTrue(du.match_device(uspec1, uspec2))

    def test_match_device_serial(self):
        # should return true if ID_SERIAL_SHORT is given
        # and if it is the same for both uspecs
        # and if DEVTYPE is given and if it is 'disk'
        uspec1 = uspec2 = {'ID_SERIAL_SHORT': 'fakeserial',
                           'DEVTYPE': 'disk'}
        self.assertTrue(du.match_device(uspec1, uspec2))

    def test_match_device_serial_false(self):
        # should return false if ID_SERIAL_SHORT is given
        # and if it does not match each other
        uspec1 = {'ID_SERIAL_SHORT': 'fakeserial1'}
        uspec2 = {'ID_SERIAL_SHORT': 'fakeserial2'}
        self.assertFalse(du.match_device(uspec1, uspec2))
