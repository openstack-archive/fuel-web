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

from fuel_agent import errors
from fuel_agent.utils import fs as fu
from fuel_agent.utils import utils


class TestFSUtils(test_base.BaseTestCase):

    @mock.patch.object(utils, 'execute')
    def test_make_fs(self, mock_exec):
        fu.make_fs('ext4', '-F', '-L fake_label', '/dev/fake')
        mock_exec.assert_called_once_with('mkfs.ext4', '-F', '-L',
                                          'fake_label', '/dev/fake')

    @mock.patch.object(utils, 'execute')
    def test_make_fs_swap(self, mock_exec):
        fu.make_fs('swap', '-f', '-L fake_label', '/dev/fake')
        mock_exec.assert_called_once_with('mkswap', '-f', '-L', 'fake_label',
                                          '/dev/fake')

    @mock.patch.object(utils, 'execute')
    def test_extend_fs_ok_ext2(self, mock_exec):
        fu.extend_fs('ext2', '/dev/fake')
        expected_calls = [
            mock.call('e2fsck', '-yf', '/dev/fake', check_exit_code=[0]),
            mock.call('resize2fs', '/dev/fake', check_exit_code=[0]),
            mock.call('e2fsck', '-pf', '/dev/fake', check_exit_code=[0])
        ]
        self.assertEqual(mock_exec.call_args_list, expected_calls)

    @mock.patch.object(utils, 'execute')
    def test_extend_fs_ok_ext3(self, mock_exec):
        fu.extend_fs('ext3', '/dev/fake')
        expected_calls = [
            mock.call('e2fsck', '-yf', '/dev/fake', check_exit_code=[0]),
            mock.call('resize2fs', '/dev/fake', check_exit_code=[0]),
            mock.call('e2fsck', '-pf', '/dev/fake', check_exit_code=[0])
        ]
        self.assertEqual(mock_exec.call_args_list, expected_calls)

    @mock.patch.object(utils, 'execute')
    def test_extend_fs_ok_ext4(self, mock_exec):
        fu.extend_fs('ext4', '/dev/fake')
        expected_calls = [
            mock.call('e2fsck', '-yf', '/dev/fake', check_exit_code=[0]),
            mock.call('resize2fs', '/dev/fake', check_exit_code=[0]),
            mock.call('e2fsck', '-pf', '/dev/fake', check_exit_code=[0])
        ]
        self.assertEqual(mock_exec.call_args_list, expected_calls)

    @mock.patch.object(utils, 'execute')
    def test_extend_fs_ok_xfs(self, mock_exec):
        fu.extend_fs('xfs', '/dev/fake')
        mock_exec.assert_called_once_with(
            'xfs_growfs', '/dev/fake', check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_extend_fs_unsupported_fs(self, mock_exec):
        self.assertRaises(errors.FsUtilsError, fu.extend_fs,
                          'unsupported', '/dev/fake')

    @mock.patch.object(utils, 'execute')
    def test_mount_fs(self, mock_exec):
        fu.mount_fs('ext3', '/dev/fake', '/target')
        mock_exec.assert_called_once_with(
            'mount', '-t', 'ext3', '/dev/fake', '/target', check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_mount_bind_no_path2(self, mock_exec):
        fu.mount_bind('/target', '/fake')
        mock_exec.assert_called_once_with(
            'mount', '--bind', '/fake', '/target/fake', check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_mount_bind_path2(self, mock_exec):
        fu.mount_bind('/target', '/fake', '/fake2')
        mock_exec.assert_called_once_with(
            'mount', '--bind', '/fake', '/target/fake2', check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_umount_fs_ok(self, mock_exec):
        fu.umount_fs('/fake')
        expected_calls = [
            mock.call('mountpoint', '-q', '/fake', check_exit_code=[0]),
            mock.call('umount', '/fake', check_exit_code=[0])
        ]
        self.assertEqual(expected_calls, mock_exec.call_args_list)

    @mock.patch.object(utils, 'execute')
    def test_umount_fs_not_mounted(self, mock_exec):
        mock_exec.side_effect = errors.ProcessExecutionError
        fu.umount_fs('/fake')
        mock_exec.assert_called_once_with(
            'mountpoint', '-q', '/fake', check_exit_code=[0])

    @mock.patch.object(utils, 'execute')
    def test_umount_fs_error(self, mock_exec):
        mock_exec.side_effect = [
            None, errors.ProcessExecutionError('message'), ('', '')]
        fu.umount_fs('/fake', try_lazy_umount=True)
        expected_calls = [
            mock.call('mountpoint', '-q', '/fake', check_exit_code=[0]),
            mock.call('umount', '/fake', check_exit_code=[0]),
            mock.call('umount', '-l', '/fake', check_exit_code=[0])
        ]
        self.assertEqual(expected_calls, mock_exec.call_args_list)

    @mock.patch.object(utils, 'execute')
    def test_umount_fs_error_lazy_false(self, mock_exec):
        mock_exec.side_effect = [
            None, errors.ProcessExecutionError('message')]
        expected_calls = [
            mock.call('mountpoint', '-q', '/fake', check_exit_code=[0]),
            mock.call('umount', '/fake', check_exit_code=[0]),
        ]
        self.assertRaises(errors.ProcessExecutionError,
                          fu.umount_fs, '/fake', try_lazy_umount=False)
        self.assertEqual(expected_calls, mock_exec.call_args_list)
