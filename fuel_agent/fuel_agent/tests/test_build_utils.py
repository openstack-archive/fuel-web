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
import signal

import mock
from oslo.config import cfg
import unittest2

from fuel_agent import errors
from fuel_agent.utils import build as bu
from fuel_agent.utils import hardware as hu
from fuel_agent.utils import utils


CONF = cfg.CONF


class BuildUtilsTestCase(unittest2.TestCase):

    _fake_ubuntu_release = '''
      Origin: TestOrigin
      Label: TestLabel
      Archive: test-archive
      Codename: testcodename
    '''

    def setUp(self):
        super(BuildUtilsTestCase, self).setUp()

    @mock.patch.object(utils, 'execute', return_value=(None, None))
    def test_run_debootstrap(self, mock_exec):
        bu.run_debootstrap('uri', 'suite', 'chroot', 'arch', attempts=2)
        mock_exec.assert_called_once_with('debootstrap', '--verbose',
                                          '--no-check-gpg', '--arch=arch',
                                          'suite', 'chroot', 'uri', attempts=2)

    @mock.patch.object(utils, 'execute', return_value=(None, None))
    def test_run_debootstrap_eatmydata(self, mock_exec):
        bu.run_debootstrap('uri', 'suite', 'chroot', 'arch', eatmydata=True,
                           attempts=2)
        mock_exec.assert_called_once_with('debootstrap', '--verbose',
                                          '--no-check-gpg', '--arch=arch',
                                          '--include=eatmydata', 'suite',
                                          'chroot', 'uri', attempts=2)

    @mock.patch.object(utils, 'execute', return_value=(None, None))
    def test_run_apt_get(self, mock_exec):
        bu.run_apt_get('chroot', ['package1', 'package2'], attempts=2)
        mock_exec_expected_calls = [
            mock.call('chroot', 'chroot', 'apt-get', '-y', 'update',
                      attempts=2),
            mock.call('chroot', 'chroot', 'apt-get', '-y', 'install',
                      'package1 package2', attempts=2)]
        self.assertEqual(mock_exec_expected_calls, mock_exec.call_args_list)

    @mock.patch.object(utils, 'execute', return_value=(None, None))
    def test_run_apt_get_eatmydata(self, mock_exec):
        bu.run_apt_get('chroot', ['package1', 'package2'], eatmydata=True,
                       attempts=2)
        mock_exec_expected_calls = [
            mock.call('chroot', 'chroot', 'apt-get', '-y', 'update',
                      attempts=2),
            mock.call('chroot', 'chroot', 'eatmydata', 'apt-get', '-y',
                      'install', 'package1 package2', attempts=2)]
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

    @mock.patch.object(os, 'fchmod')
    @mock.patch.object(os, 'path')
    def test_suppress_services_start_nomkdir(self, mock_path, mock_fchmod):
        mock_path.join.return_value = 'fake_path'
        mock_path.exists.return_value = True
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            file_handle_mock.fileno.return_value = 'fake_fileno'
            bu.suppress_services_start('chroot')
            mock_open.assert_called_once_with('fake_path', 'w')
            expected = '#!/bin/sh\n# prevent any service from being started\n'\
                       'exit 101\n'
            file_handle_mock.write.assert_called_once_with(expected)
            mock_fchmod.assert_called_once_with('fake_fileno', 0o755)

    @mock.patch.object(shutil, 'rmtree')
    @mock.patch.object(os, 'makedirs')
    @mock.patch.object(os, 'path')
    def test_clean_dirs(self, mock_path, mock_mkdir, mock_rmtree):
        mock_path.isdir.return_value = True
        dirs = ['dir1', 'dir2', 'dir3']
        mock_path.join.side_effect = dirs
        bu.clean_dirs('chroot', dirs)
        for m in (mock_rmtree, mock_mkdir):
            self.assertEqual([mock.call(d) for d in dirs], m.call_args_list)

    @mock.patch.object(os, 'path')
    def test_clean_dirs_not_isdir(self, mock_path):
        mock_path.isdir.return_value = False
        dirs = ['dir1', 'dir2', 'dir3']
        mock_path.join.side_effect = dirs
        bu.clean_dirs('chroot', dirs)
        self.assertEqual([mock.call('chroot', d) for d in dirs],
                         mock_path.join.call_args_list)

    @mock.patch.object(os, 'remove')
    @mock.patch.object(os, 'path')
    def test_remove_files(self, mock_path, mock_remove):
        mock_path.exists.return_value = True
        files = ['file1', 'file2', 'dir3']
        mock_path.join.side_effect = files
        bu.remove_files('chroot', files)
        self.assertEqual([mock.call(f) for f in files],
                         mock_remove.call_args_list)

    @mock.patch.object(os, 'path')
    def test_remove_files_not_exists(self, mock_path):
        mock_path.exists.return_value = False
        files = ['file1', 'file2', 'dir3']
        mock_path.join.side_effect = files
        bu.remove_files('chroot', files)
        self.assertEqual([mock.call('chroot', f) for f in files],
                         mock_path.join.call_args_list)

    @mock.patch.object(bu, 'remove_files')
    @mock.patch.object(bu, 'clean_dirs')
    def test_clean_apt_settings(self, mock_dirs, mock_files):
        bu.clean_apt_settings('chroot', 'unsigned', 'force_ipv4')
        mock_dirs.assert_called_once_with(
            'chroot', ['etc/apt/preferences.d', 'etc/apt/sources.list.d'])
        mock_files.assert_called_once_with(
            'chroot', ['etc/apt/sources.list', 'etc/apt/preferences',
                       'etc/apt/apt.conf.d/%s' % 'force_ipv4',
                       'etc/apt/apt.conf.d/%s' % 'unsigned'])

    @mock.patch('fuel_agent.utils.build.open',
                create=True, new_callable=mock.mock_open)
    @mock.patch.object(os, 'path')
    @mock.patch.object(bu, 'clean_apt_settings')
    @mock.patch.object(bu, 'remove_files')
    @mock.patch.object(utils, 'execute')
    def test_do_post_inst(self, mock_exec, mock_files, mock_clean, mock_path,
                          mock_open):
        mock_path.join.return_value = 'fake_path'
        bu.do_post_inst('chroot')
        file_handle_mock = mock_open.return_value.__enter__.return_value
        file_handle_mock.write.assert_called_once_with('manual\n')
        mock_exec_expected_calls = [
            mock.call('sed', '-i', 's%root:[\*,\!]%root:$6$IInX3Cqo$5xytL1VZb'
                      'ZTusOewFnG6couuF0Ia61yS3rbC6P5YbZP2TYclwHqMq9e3Tg8rvQx'
                      'hxSlBXP1DZhdUamxdOBXK0.%', 'fake_path'),
            mock.call('chroot', 'chroot', 'update-rc.d', 'puppet', 'disable')]
        self.assertEqual(mock_exec_expected_calls, mock_exec.call_args_list)
        mock_files.assert_called_once_with('chroot', ['usr/sbin/policy-rc.d'])
        mock_clean.assert_called_once_with('chroot')
        mock_path_join_expected_calls = [
            mock.call('chroot', 'etc/shadow'),
            mock.call('chroot', 'etc/init/mcollective.override')]
        self.assertEqual(mock_path_join_expected_calls,
                         mock_path.join.call_args_list)

    @mock.patch('fuel_agent.utils.build.open',
                create=True, new_callable=mock.mock_open)
    @mock.patch('fuel_agent.utils.build.time.sleep')
    @mock.patch.object(os, 'kill')
    @mock.patch.object(os, 'readlink', return_value='chroot')
    @mock.patch.object(utils, 'execute')
    def test_stop_chrooted_processes(self, mock_exec, mock_link,
                                     mock_kill, mock_sleep, mock_open):
        mock_exec.side_effect = [
            ('kernel   951  1641  1700  1920  3210  4104', ''),
            ('kernel   951  1641  1700', ''),
            ('', '')]
        mock_exec_expected_calls = \
            [mock.call('fuser', '-v', 'chroot', check_exit_code=False)] * 3

        bu.stop_chrooted_processes('chroot', signal=signal.SIGTERM)
        self.assertEqual(mock_exec_expected_calls, mock_exec.call_args_list)

        expected_mock_link_calls = [
            mock.call('/proc/951/root'),
            mock.call('/proc/1641/root'),
            mock.call('/proc/1700/root'),
            mock.call('/proc/1920/root'),
            mock.call('/proc/3210/root'),
            mock.call('/proc/4104/root'),
            mock.call('/proc/951/root'),
            mock.call('/proc/1641/root'),
            mock.call('/proc/1700/root')]
        expected_mock_kill_calls = [
            mock.call(951, signal.SIGTERM),
            mock.call(1641, signal.SIGTERM),
            mock.call(1700, signal.SIGTERM),
            mock.call(1920, signal.SIGTERM),
            mock.call(3210, signal.SIGTERM),
            mock.call(4104, signal.SIGTERM),
            mock.call(951, signal.SIGTERM),
            mock.call(1641, signal.SIGTERM),
            mock.call(1700, signal.SIGTERM)]
        self.assertEqual(expected_mock_link_calls, mock_link.call_args_list)
        self.assertEqual(expected_mock_kill_calls, mock_kill.call_args_list)

    @mock.patch.object(os, 'makedev', return_value='fake_dev')
    @mock.patch.object(os, 'mknod')
    @mock.patch.object(os, 'path')
    @mock.patch.object(utils, 'execute', return_value=('/dev/loop123\n', ''))
    def test_get_free_loop_device_ok(self, mock_exec, mock_path, mock_mknod,
                                     mock_mkdev):
        mock_path.exists.return_value = False
        self.assertEqual('/dev/loop123', bu.get_free_loop_device(1))
        mock_exec.assert_called_once_with('losetup', '--find')
        mock_path.exists.assert_called_once_with('/dev/loop0')
        mock_mknod.assert_called_once_with('/dev/loop0', 25008, 'fake_dev')
        mock_mkdev.assert_called_once_with(1, 0)

    def test_set_apt_get_env(self):
        with mock.patch.dict('os.environ', {}):
            bu.set_apt_get_env()
            self.assertEqual('noninteractive', os.environ['DEBIAN_FRONTEND'])
            self.assertEqual('true', os.environ['DEBCONF_NONINTERACTIVE_SEEN'])
            for var in ('LC_ALL', 'LANG', 'LANGUAGE'):
                self.assertEqual('C', os.environ[var])

    def test_strip_filename(self):
        self.assertEqual('safe_Tex.-98',
                         bu.strip_filename('!@$^^^safe _Tex.?-98;'))

    @mock.patch.object(os, 'makedev', return_value='fake_dev')
    @mock.patch.object(os, 'mknod')
    @mock.patch.object(os, 'path')
    @mock.patch.object(utils, 'execute', return_value=('', 'Error!!!'))
    def test_get_free_loop_device_not_found(self, mock_exec, mock_path,
                                            mock_mknod, mock_mkdev):
        mock_path.exists.return_value = False
        self.assertRaises(errors.NoFreeLoopDevices, bu.get_free_loop_device)

    @mock.patch('tempfile.NamedTemporaryFile')
    @mock.patch.object(utils, 'execute')
    def test_create_sparse_tmp_file(self, mock_exec, mock_temp):
        tmp_file = mock.Mock()
        tmp_file.name = 'fake_name'
        mock_temp.return_value = tmp_file
        bu.create_sparse_tmp_file('dir', 'suffix', 1)
        mock_temp.assert_called_once_with(dir='dir', suffix='suffix',
                                          delete=False)
        mock_exec.assert_called_once_with('truncate', '-s', '1M',
                                          tmp_file.name)

    @mock.patch.object(utils, 'execute')
    def test_attach_file_to_loop(self, mock_exec):
        bu.attach_file_to_loop('file', 'loop')
        mock_exec.assert_called_once_with('losetup', 'loop', 'file')

    @mock.patch.object(utils, 'execute')
    def test_deattach_loop(self, mock_exec):
        mock_exec.return_value = ('/dev/loop0: [fd03]:130820 (/dev/loop0)', '')
        bu.deattach_loop('/dev/loop0', check_exit_code='Fake')
        mock_exec_expected_calls = [
            mock.call('losetup', '-a'),
            mock.call('losetup', '-d', '/dev/loop0', check_exit_code='Fake')
        ]
        self.assertEqual(mock_exec.call_args_list, mock_exec_expected_calls)

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
            expected_calls = [mock.call('deb uri1 suite1 section1\n')]
            self.assertEqual(expected_calls,
                             file_handle_mock.write.call_args_list)
        expected_mock_path_calls = [
            mock.call('chroot', 'etc/apt/sources.list.d',
                      'fuel-image-name1.list')]
        self.assertEqual(expected_mock_path_calls,
                         mock_path.join.call_args_list)

    @mock.patch.object(os, 'path')
    def test_add_apt_source_no_section(self, mock_path):
        mock_path.return_value = 'fake_path'
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            bu.add_apt_source('name2', 'uri2', 'suite2', None, 'chroot')
            expected_calls = [mock.call('deb uri2 suite2\n')]
            self.assertEqual(expected_calls,
                             file_handle_mock.write.call_args_list)
        expected_mock_path_calls = [
            mock.call('chroot', 'etc/apt/sources.list.d',
                      'fuel-image-name2.list')]
        self.assertEqual(expected_mock_path_calls,
                         mock_path.join.call_args_list)

    @mock.patch.object(os, 'path')
    @mock.patch('fuel_agent.utils.build.utils.init_http_request',
                return_value=mock.Mock(text=_fake_ubuntu_release))
    def test_add_apt_preference(self, mock_get, mock_path):
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value

            fake_section = 'section1'
            bu.add_apt_preference(
                'name1',
                123,
                'test-archive',
                fake_section,
                'chroot',
                'http://test-uri'
            )

            calls_args = [
                c[0][0] for c in file_handle_mock.write.call_args_list
            ]

            self.assertEqual(len(calls_args), 4)
            self.assertEqual(calls_args[0], 'Package: *\n')
            self.assertEqual(calls_args[1], 'Pin: release ')
            self.assertIn("l=TestLabel", calls_args[2])
            self.assertIn("n=testcodename", calls_args[2])
            self.assertIn("a=test-archive", calls_args[2])
            self.assertIn("o=TestOrigin", calls_args[2])
            self.assertIn("c=section1", calls_args[2])
            self.assertEqual(calls_args[3], 'Pin-Priority: 123\n')

        expected_mock_path_calls = [
            mock.call('http://test-uri', 'dists', 'test-archive', 'Release'),
            mock.call('chroot', 'etc/apt/preferences.d',
                      'fuel-image-name1.pref')]
        self.assertEqual(expected_mock_path_calls,
                         mock_path.join.call_args_list)

    @mock.patch.object(os, 'path')
    @mock.patch('fuel_agent.utils.build.utils.init_http_request',
                return_value=mock.Mock(text=_fake_ubuntu_release))
    def test_add_apt_preference_multuple_sections(self, mock_get, mock_path):
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            fake_sections = ['section2', 'section3']
            bu.add_apt_preference('name3', 234, 'test-archive',
                                  ' '.join(fake_sections),
                                  'chroot', 'http://test-uri')

            calls_args = [
                c[0][0] for c in file_handle_mock.write.call_args_list
            ]

            calls_package = [c for c in calls_args if c == 'Package: *\n']
            calls_pin = [c for c in calls_args if c == 'Pin: release ']
            calls_pin_p = [c for c in calls_args if c == 'Pin-Priority: 234\n']
            first_section = [
                c for c in calls_args if 'c={0}'.format(fake_sections[0]) in c
            ]
            second_section = [
                c for c in calls_args if 'c={0}'.format(fake_sections[1]) in c
            ]
            self.assertEqual(len(calls_package), len(fake_sections))
            self.assertEqual(len(calls_pin), len(fake_sections))
            self.assertEqual(len(calls_pin_p), len(fake_sections))
            self.assertEqual(len(first_section), 1)
            self.assertEqual(len(second_section), 1)

            for pin_line in calls_args[2::4]:
                self.assertIn("l=TestLabel", pin_line)
                self.assertIn("n=testcodename", pin_line)
                self.assertIn("a=test-archive", pin_line)
                self.assertIn("o=TestOrigin", pin_line)

        expected_mock_path_calls = [
            mock.call('http://test-uri', 'dists', 'test-archive', 'Release'),
            mock.call('chroot', 'etc/apt/preferences.d',
                      'fuel-image-name3.pref')]
        self.assertEqual(expected_mock_path_calls,
                         mock_path.join.call_args_list)

    @mock.patch.object(os, 'path')
    @mock.patch('fuel_agent.utils.build.utils.init_http_request',
                return_value=mock.Mock(text=_fake_ubuntu_release))
    def test_add_apt_preference_no_sections(self, mock_get, mock_path):
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value

            bu.add_apt_preference(
                'name1',
                123,
                'test-archive',
                '',
                'chroot',
                'http://test-uri'
            )

            calls_args = [
                c[0][0] for c in file_handle_mock.write.call_args_list
            ]

            self.assertEqual(len(calls_args), 4)
            self.assertEqual(calls_args[0], 'Package: *\n')
            self.assertEqual(calls_args[1], 'Pin: release ')
            self.assertIn("l=TestLabel", calls_args[2])
            self.assertIn("n=testcodename", calls_args[2])
            self.assertIn("a=test-archive", calls_args[2])
            self.assertIn("o=TestOrigin", calls_args[2])
            self.assertNotIn("c=", calls_args[2])
            self.assertEqual(calls_args[3], 'Pin-Priority: 123\n')

        expected_mock_path_calls = [
            mock.call('http://test-uri', 'test-archive', 'Release'),
            mock.call('chroot', 'etc/apt/preferences.d',
                      'fuel-image-name1.pref')]
        self.assertEqual(expected_mock_path_calls,
                         mock_path.join.call_args_list)

    @mock.patch.object(bu, 'clean_apt_settings')
    @mock.patch.object(os, 'path')
    def test_pre_apt_get(self, mock_path, mock_clean):
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            bu.pre_apt_get('chroot')
            expected_calls = [
                mock.call('APT::Get::AllowUnauthenticated 1;\n'),
                mock.call('Acquire::ForceIPv4 "true";\n')]
            self.assertEqual(expected_calls,
                             file_handle_mock.write.call_args_list)
        mock_clean.assert_called_once_with('chroot')
        expected_join_calls = [
            mock.call('chroot', 'etc/apt/apt.conf.d',
                      CONF.allow_unsigned_file),
            mock.call('chroot', 'etc/apt/apt.conf.d',
                      CONF.force_ipv4_file)]
        self.assertEqual(expected_join_calls, mock_path.join.call_args_list)

    @mock.patch('gzip.open')
    @mock.patch.object(os, 'remove')
    def test_containerize_gzip(self, mock_remove, mock_gzip):
        with mock.patch('six.moves.builtins.open', create=True) as mock_open:
            file_handle_mock = mock_open.return_value.__enter__.return_value
            file_handle_mock.read.side_effect = ['test data', '']
            g = mock.Mock()
            mock_gzip.return_value = g
            self.assertEqual('file.gz', bu.containerize('file', 'gzip', 1))
            g.write.assert_called_once_with('test data')
            expected_calls = [mock.call(1), mock.call(1)]
            self.assertEqual(expected_calls,
                             file_handle_mock.read.call_args_list)
        mock_remove.assert_called_once_with('file')

    def test_containerize_bad_container(self):
        self.assertRaises(errors.WrongImageDataError, bu.containerize, 'file',
                          'fake')
