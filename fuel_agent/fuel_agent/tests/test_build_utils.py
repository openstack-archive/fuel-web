#    Copyright 2015 Mirantis, Inc.
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
import shutil
import testtools

import mock
from oslo.config import cfg

from fuel_agent.utils import build_utils as bu
from fuel_agent.utils import utils


CONF = cfg.CONF


class BuildUtilsTestCase(testtools.TestCase):
    def setUp(self):
        super(BuildUtilsTestCase, self).setUp()

    @mock.patch.object(utils, 'execute')
    def test_run_debootstrap(self, mock_exec):
        mock_exec.return_value = (None, None)
        bu.run_debootstrap('uri', 'suite', 'chroot', 'arch')
        mock_exec.assert_called_once_with('debootstrap', '--verbose',
                                          '--no-check-gpg', '--arch=arch',
                                          'suite', 'chroot', 'uri')

    @mock.patch.object(utils, 'execute')
    def test_run_apt_get(self, mock_exec):
        mock_exec.return_value = (None, None)
        bu.run_apt_get('chroot', ['package1', 'package2'])
        mock_exec_expected_calls = [
            mock.call('chroot', 'chroot', 'apt-get', '-y', 'update'),
            mock.call('chroot', 'chroot', 'apt-get', '-y', 'install',
                      'package1 package2')]
        self.assertEqual(mock_exec_expected_calls, mock_exec.call_args_list)

    @mock.patch.object(os, 'fchmod')
    @mock.patch.object(os, 'makedirs')
    @mock.patch.object(os, 'path')
    def test_suppress_services_start(self, mock_path, mock_mkdir, mock_fchmod):
        mock_path.join.return_value = 'fake_path'
        mock_path.exists.return_value = False
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            file_handle_mock.fileno.return_value = 'fake_fileno'
            bu.suppress_services_start('chroot')
            mock_open.assert_called_once_with('fake_path', 'w')
            expected = '#!/bin/sh\n# prevent any service from being started\n'\
                       'exit 101\n'
            file_handle_mock.write.assert_called_once_with(expected)
            mock_fchmod.assert_called_once_with('fake_fileno', 0o755)
        mock_mkdir.assert_called_once_with('fake_path')

    @mock.patch.object(shutil, 'rmtree')
    @mock.patch.object(os, 'makedirs')
    @mock.patch.object(os, 'path')
    def test_remove_dirs(self, mock_path, mock_mkdir, mock_rmtree):
        mock_path.isdir.return_value = True
        dirs = ['dir1', 'dir2', 'dir3']
        mock_path.join.side_effect = dirs
        bu.remove_dirs('chroot', dirs)
        for m in (mock_rmtree, mock_mkdir):
            self.assertEqual([mock.call(d) for d in dirs], m.call_args_list)

    @mock.patch.object(os, 'remove')
    @mock.patch.object(os, 'path')
    def test_remove_files(self, mock_path, mock_remove):
        mock_path.exists.return_value = True
        files = ['file1', 'file2', 'dir3']
        mock_path.join.side_effect = files
        bu.remove_files('chroot', files)
        self.assertEqual([mock.call(f) for f in files],
                         mock_remove.call_args_list)

    @mock.patch.object(bu, 'remove_files')
    @mock.patch.object(bu, 'remove_dirs')
    def test_clean_apt(self, mock_dirs, mock_files):
        bu.clean_apt('chroot')
        mock_dirs.assert_called_once_with(
            'chroot', ['etc/apt/preferences.d', 'etc/apt/sources.list.d'])
        mock_files.assert_called_once_with(
            'chroot', ['etc/apt/sources.list', 'etc/apt/preferences',
                       'etc/apt/apt.conf.d/02mirantis-unauthenticated'])

    @mock.patch.object(os, 'path')
    @mock.patch.object(bu, 'clean_apt')
    @mock.patch.object(bu, 'remove_files')
    @mock.patch.object(utils, 'execute')
    def test_do_post_inst(self, mock_exec, mock_files, mock_clean, mock_path):
        mock_path.join.return_value = 'fake_path'
        bu.do_post_inst('chroot')
        mock_exec.assert_called_once_with(
            'sed', '-i', 's%root:[\*,\!]%root:$6$IInX3Cqo$5xytL1VZbZTusO'
            'ewFnG6couuF0Ia61yS3rbC6P5YbZP2TYclwHqMq9e3Tg8rvQxhxSlBXP1DZ'
            'hdUamxdOBXK0.%', 'fake_path')
        mock_files.assert_called_once_with('chroot', ['usr/sbin/policy-rc.d'])
        mock_clean.assert_called_once_with('chroot')
        mock_path.join.assert_called_once_with('chroot', 'etc/shadow')
