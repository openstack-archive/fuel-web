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
from oslotest import base as test_base
import time

from fuel_agent import errors
from fuel_agent.utils import partition_utils as pu
from fuel_agent.utils import utils


class TestPartitionUtils(test_base.BaseTestCase):
    @mock.patch.object(pu, 'make_label')
    def test_wipe(self, mock_label):
        # should run call make_label method
        # in order to create new empty table which we think
        # is equivalent to wiping the old one
        pu.wipe('/dev/fake')
        mock_label.assert_called_once_with('/dev/fake')

    @mock.patch.object(pu, 'reread_partitions')
    @mock.patch.object(utils, 'execute')
    def test_make_label(self, mock_exec, mock_rerd):
        # should run parted OS command
        # in order to create label on a device
        mock_exec.return_value = ('out', '')

        # gpt by default
        pu.make_label('/dev/fake')
        mock_exec.assert_called_once_with(
            'parted', '-s', '/dev/fake',
            'mklabel', 'gpt', check_exit_code=[0, 1])
        mock_rerd.assert_called_once_with('/dev/fake', out='out')
        mock_exec.reset_mock()
        mock_rerd.reset_mock()

        # label is set explicitly
        pu.make_label('/dev/fake', label='msdos')
        mock_exec.assert_called_once_with(
            'parted', '-s', '/dev/fake',
            'mklabel', 'msdos', check_exit_code=[0, 1])
        mock_rerd.assert_called_once_with('/dev/fake', out='out')

    def test_make_label_wrong_label(self):
        # should check if label is valid
        # should raise exception if it is not
        self.assertRaises(errors.WrongPartitionLabelError,
                          pu.make_label, '/dev/fake', 'wrong')

    def test_get_set_partition_flag_cmd(self):
        # should run parted OS command
        # in order to set flag on a partition

        # default state is 'on'
        expected_return = ['set', '1', 'boot', 'on']
        self.assertEqual(expected_return,
                         pu.get_set_partition_flag_cmd('/dev/fake', 1, 'boot'))

        # if state argument is given use it
        expected_return = ['set', '1', 'boot', 'off']
        self.assertEqual(expected_return,
                         pu.get_set_partition_flag_cmd('/dev/fake', 1, 'boot',
                                                       state='off'))

    def test_get_set_partition_flag_cmd_wrong_flag(self):
        # should check if flag is valid
        # should raise exception if it is not
        self.assertRaises(errors.WrongPartitionSchemeError,
                          pu.get_set_partition_flag_cmd,
                          '/dev/fake', 1, 'wrong')

    def test_get_set_partition_flag_cmd_wrong_state(self):
        # should check if flag is valid
        # should raise exception if it is not
        self.assertRaises(errors.WrongPartitionSchemeError,
                          pu.get_set_partition_flag_cmd,
                          '/dev/fake', 1, 'boot', state='wrong')

    @mock.patch.object(pu, 'info')
    def test_get_make_partition_cmd(self, mock_info):
        # should run parted OS command
        # in order to create new partition

        mock_info.return_value = {
            'parts': [
                {'begin': 0, 'end': 1000, 'fstype': 'free'},
            ]
        }
        expected_return = ['mkpart', 'primary', '100', '200']
        self.assertEqual(expected_return,
                         pu.get_make_partition_cmd('/dev/fake', 100, 200,
                                                   'primary'))

    def test_get_make_partition_cmd_wrong_ptype(self):
        # should check if partition type is one of
        # 'primary' or 'logical'
        # should raise exception if it is not
        self.assertRaises(errors.WrongPartitionSchemeError,
                          pu.get_make_partition_cmd,
                          '/dev/fake', 200, 100, 'wrong')

    def test_get_make_partition_cmd_begin_overlaps_end(self):
        # should check if begin is less than end
        # should raise exception if it isn't
        self.assertRaises(errors.WrongPartitionSchemeError,
                          pu.get_make_partition_cmd,
                          '/dev/fake', 200, 100, 'primary')

    @mock.patch.object(pu, 'info')
    def test_get_make_partition_cmd_overlaps_other_parts(self, mock_info):
        # should check if begin or end overlap other partitions
        # should raise exception if it does
        mock_info.return_value = {
            'parts': [
                {'begin': 0, 'end': 100, 'fstype': 'free'},
                {'begin': 100, 'end': 200, 'fstype': 'notfree'},
                {'begin': 200, 'end': 300, 'fstype': 'free'}
            ]
        }
        self.assertRaises(errors.WrongPartitionSchemeError,
                          pu.get_make_partition_cmd,
                          '/dev/fake', 99, 101, 'primary')
        self.assertRaises(errors.WrongPartitionSchemeError,
                          pu.get_make_partition_cmd,
                          '/dev/fake', 100, 200, 'primary')
        self.assertRaises(errors.WrongPartitionSchemeError,
                          pu.get_make_partition_cmd,
                          '/dev/fake', 200, 301, 'primary')
        self.assertEqual(mock_info.call_args_list,
                         [mock.call('/dev/fake')] * 3)

    @mock.patch.object(pu, 'reread_partitions')
    @mock.patch.object(pu, 'info')
    @mock.patch.object(utils, 'execute')
    def test_remove_partition(self, mock_exec, mock_info, mock_rerd):
        # should run parted OS command
        # in order to remove partition
        mock_exec.return_value = ('out', '')
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
        pu.remove_partition('/dev/fake', 1)
        mock_exec.assert_called_once_with(
            'parted', '-s', '/dev/fake', 'rm', '1', check_exit_code=[0])
        mock_rerd.assert_called_once_with('/dev/fake', out='out')

    @mock.patch.object(pu, 'info')
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
        self.assertRaises(errors.PartitionNotFoundError, pu.remove_partition,
                          '/dev/fake', 3)

    @mock.patch.object(utils, 'execute')
    def test_set_gpt_type(self, mock_exec):
        pu.set_gpt_type('dev', 'num', 'type')
        mock_exec.assert_called_once_with('sgdisk',
                                          '--typecode=%s:%s' % ('num', 'type'),
                                          'dev', check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_info(self, mock_exec):
        mock_exec.return_value = [
            'BYT;\n'
            '/dev/fake:476940MiB:scsi:512:4096:msdos:ATA 1BD14;\n'
            '1:0.03MiB:1.00MiB:0.97MiB:free;\n'
            '1:1.00MiB:191MiB:190MiB:ext3::boot;\n'
            '2:191MiB:476939MiB:476748MiB:::lvm;\n'
            '1:476939MiB:476940MiB:1.02MiB:free;\n'
        ]
        expected = {'generic': {'dev': '/dev/fake',
                                'logical_block': 512,
                                'model': 'ATA 1BD14',
                                'physical_block': 4096,
                                'size': 476940,
                                'table': 'msdos'},

                    'parts': [{'begin': 1, 'end': 1, 'fstype': 'free',
                               'num': 1, 'size': 1},
                              {'begin': 1, 'end': 191, 'fstype': 'ext3',
                               'num': 1, 'size': 190},
                              {'begin': 191, 'end': 476939, 'fstype': None,
                               'num': 2, 'size': 476748},
                              {'begin': 476939, 'end': 476940,
                               'fstype': 'free', 'num': 1, 'size': 2}]}
        actual = pu.info('/dev/fake')
        self.assertEqual(expected, actual)
        mock_exec.assert_called_once_with('parted', '-s', '/dev/fake', '-m',
                                          'unit', 'MiB', 'print', 'free',
                                          check_exit_code=[0, 1])

    @mock.patch.object(utils, 'execute')
    def test_reread_partitions_ok(self, mock_exec):
        pu.reread_partitions('/dev/fake', out='')
        self.assertEqual(mock_exec.call_args_list, [])

    @mock.patch.object(time, 'sleep')
    @mock.patch.object(utils, 'execute')
    def test_reread_partitions_device_busy(self, mock_exec, mock_sleep):
        mock_exec.return_value = ('', '')
        pu.reread_partitions('/dev/fake', out='_Device or resource busy_')
        mock_exec_expected = [
            mock.call('partprobe', '/dev/fake', check_exit_code=[0, 1]),
            mock.call('partx', '-a', '/dev/fake', check_exit_code=[0, 1])
        ]
        self.assertEqual(mock_exec.call_args_list, mock_exec_expected)
        mock_sleep.assert_called_once_with(1)

    @mock.patch.object(utils, 'execute')
    def test_reread_partitions_timeout(self, mock_exec):
        self.assertRaises(errors.BaseError, pu.reread_partitions,
                          '/dev/fake', out='Device or resource busy',
                          timeout=-40)
