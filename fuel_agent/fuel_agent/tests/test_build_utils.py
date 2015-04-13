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

from fuel_agent import errors
from fuel_agent.utils import build_utils as bu
from fuel_agent.utils import hardware_utils as hu
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
                       'etc/apt/apt.conf.d/%s' % CONF.allow_unsigned_file])

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

    @mock.patch.object(os, 'kill')
    @mock.patch.object(os, 'readlink')
    @mock.patch.object(utils, 'execute')
    def test_signal_chrooted_processes(self, mock_exec, mock_link, mock_kill):
        mock_exec.return_value = ('kernel   951  1641  1700  1920  3210  4104',
                                  '')
        mock_link.return_value = 'chroot'
        bu.signal_chrooted_processes('chroot', 'signal')
        mock_exec.assert_called_once_with('fuser', '-v', 'chroot',
                                          check_exit_code=False)
        expected_mock_link_calls = [
            mock.call('/proc/951/root'),
            mock.call('/proc/1641/root'),
            mock.call('/proc/1700/root'),
            mock.call('/proc/1920/root'),
            mock.call('/proc/3210/root'),
            mock.call('/proc/4104/root')]
        expected_mock_kill_calls = [
            mock.call(951, 'signal'),
            mock.call(1641, 'signal'),
            mock.call(1700, 'signal'),
            mock.call(1920, 'signal'),
            mock.call(3210, 'signal'),
            mock.call(4104, 'signal')]
        self.assertEqual(expected_mock_link_calls, mock_link.call_args_list)
        self.assertEqual(expected_mock_kill_calls, mock_kill.call_args_list)

    @mock.patch.object(os, 'makedev')
    @mock.patch.object(os, 'mknod')
    @mock.patch.object(os, 'path')
    @mock.patch.object(utils, 'execute')
    def test_get_free_loop_ok(self, mock_exec, mock_path, mock_mknod,
                              mock_mkdev):
        mock_exec.return_value = ('/dev/loop123\n', '')
        mock_path.exists.return_value = False
        mock_mkdev.return_value = 'fake_dev'
        self.assertEqual('/dev/loop123', bu.get_free_loop())
        mock_exec.assert_called_once_with('losetup', '--find')
        mock_path.exists.assert_called_once_with('/dev/loop0')
        mock_mknod.assert_called_once_with('/dev/loop0', 25008, 'fake_dev')
        mock_mkdev.assert_called_once_with(CONF.loop_dev_major, 0)

    @mock.patch.object(os, 'makedev')
    @mock.patch.object(os, 'mknod')
    @mock.patch.object(os, 'path')
    @mock.patch.object(utils, 'execute')
    def test_get_free_loop_not_found(self, mock_exec, mock_path, mock_mknod,
                                     mock_mkdev):
        mock_exec.return_value = ('', 'Error!!!')
        mock_path.exists.return_value = False
        mock_mkdev.return_value = 'fake_dev'
        self.assertRaises(errors.NoFreeLoopDevices, bu.get_free_loop)

    @mock.patch('tempfile.NamedTemporaryFile')
    @mock.patch.object(utils, 'execute')
    def test_create_sparse_tmp_file(self, mock_exec, mock_temp):
        tmp_file = mock.Mock()
        tmp_file.name = 'fake_name'
        mock_temp.return_value = tmp_file
        bu.create_sparse_tmp_file('dir', 'suffix')
        mock_temp.assert_called_once_with(dir='dir', suffix='suffix',
                                          delete=False)
        mock_exec.assert_called_once_with('truncate', '-s',
                                          '%sM' % CONF.sparse_file_size,
                                          tmp_file.name)

    @mock.patch.object(utils, 'execute')
    def test_attach_file_to_loop(self, mock_exec):
        bu.attach_file_to_loop('loop', 'file')
        mock_exec.assert_called_once_with('losetup', 'loop', 'file')

    @mock.patch.object(utils, 'execute')
    def test_deattach_loop(self, mock_exec):
        bu.deattach_loop('loop')
        mock_exec.assert_called_once_with('losetup', '-d', 'loop')

    @mock.patch.object(hu, 'parse_simple_kv')
    @mock.patch.object(utils, 'execute')
    def test_shrink_sparse_file(self, mock_exec, mock_parse):
        mock_parse.return_value = {'block count': 1, 'block size': 2}
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            bu.shrink_sparse_file('file')
            mock_open.assert_called_once_with('file', 'rwb+')
            file_handle_mock.truncate.assert_called_once_with(1 * 2)
        expected_mock_exec_calls = [mock.call('e2fsck', '-y', '-f', 'file'),
                                    mock.call('resize2fs', '-F', '-M', 'file')]
        mock_parse.assert_called_once_with('dumpe2fs', 'file')
        self.assertEqual(expected_mock_exec_calls, mock_exec.call_args_list)

    @mock.patch.object(os, 'path')
    def test_add_apt_source(self, mock_path):
        mock_path.return_value = 'fake_path'
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            bu.add_apt_source('name1', 'uri1', 'suite1', 'section1', 'chroot')
            bu.add_apt_source('name2', 'uri2', 'suite2', None, 'chroot')
            expected_calls = [mock.call('deb uri1 suite1 section1\n'),
                              mock.call('deb uri2 suite2\n')]
            self.assertEqual(expected_calls,
                             file_handle_mock.write.call_args_list)
        expected_mock_path_calls = [
            mock.call('chroot', 'etc/apt/sources.list.d',
                      'fuel-image-name1.list'),
            mock.call('chroot', 'etc/apt/sources.list.d',
                      'fuel-image-name2.list')]
        self.assertEqual(expected_mock_path_calls,
                         mock_path.join.call_args_list)

    @mock.patch.object(os, 'path')
    def test_add_apt_preference(self, mock_path):
        mock_path.return_value = 'fake_path'
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            bu.add_apt_preference('name1', 123, 'suite1', 'section1', 'chroot')
            bu.add_apt_preference('name2', None, 'suite1', 'section1',
                                  'chroot')
            bu.add_apt_preference('name3', 234, 'suite1', 'section2 section3',
                                  'chroot')
            expected_calls = [
                mock.call('Package: *\n'),
                mock.call('Pin: release a=suite1,c=section1\n'),
                mock.call('Pin-Priority: 123\n'),
                mock.call('Package: *\n'),
                mock.call('Pin: release a=suite1,c=section2\n'),
                mock.call('Pin: release a=suite1,c=section3\n'),
                mock.call('Pin-Priority: 234\n')]
            self.assertEqual(expected_calls,
                             file_handle_mock.write.call_args_list)
        expected_mock_path_calls = [
            mock.call('chroot', 'etc/apt/preferences.d',
                      'fuel-image-name1.pref'),
            mock.call('chroot', 'etc/apt/preferences.d',
                      'fuel-image-name3.pref')]
        self.assertEqual(expected_mock_path_calls,
                         mock_path.join.call_args_list)

    @mock.patch.object(bu, 'clean_apt')
    @mock.patch.object(os, 'path')
    def test_pre_apt_get(self, mock_path, mock_clean):
        mock_path.join.return_value = 'fake_path'
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            bu.pre_apt_get('chroot')
            file_handle_mock.write.assert_called_once_with(
                'APT::Get::AllowUnauthenticated 1;\n')
        mock_clean.assert_called_once_with('chroot')
        mock_path.join.assert_called_once_with('chroot', 'etc/apt/apt.conf.d',
                                               CONF.allow_unsigned_file)

    @mock.patch('gzip.open')
    @mock.patch.object(os, 'remove')
    def test_containerize_gzip(self, mock_remove, mock_gzip):
        CONF.data_chunk_size = 1
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            file_handle_mock.read.side_effect = ['test data', '']
            g = mock.Mock()
            mock_gzip.return_value = g
            self.assertEqual('file.gz', bu.containerize('file', 'gzip'))
            g.write.assert_called_once_with('test data')
            expected_calls = [mock.call(1), mock.call(1)]
            self.assertEqual(expected_calls,
                             file_handle_mock.read.call_args_list)
        mock_remove.assert_called_once_with('file')

    def test_containerize_bad_container(self):
        self.assertRaises(errors.WrongImageDataError, bu.containerize, 'file',
                          'fake')
