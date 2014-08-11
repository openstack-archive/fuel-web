# -*- coding: utf-8 -*-

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

import StringIO
import subprocess
import urllib2

import mock
from mock import patch

from fuel_upgrade import errors
from fuel_upgrade.tests.base import BaseTestCase
from fuel_upgrade import utils
from fuel_upgrade.utils import create_dir_if_not_exists
from fuel_upgrade.utils import exec_cmd
from fuel_upgrade.utils import exec_cmd_iterator
from fuel_upgrade.utils import get_request
from fuel_upgrade.utils import topological_sorting
from fuel_upgrade.utils import wait_for_true


class TestUtils(BaseTestCase):

    def make_process_mock(self, return_code=0):
        process_mock = mock.Mock()
        process_mock.stdout = ['Stdout line 1', 'Stdout line 2']
        process_mock.returncode = return_code

        return process_mock

    def test_exec_cmd_executes_sucessfuly(self):
        cmd = 'some command'

        process_mock = self.make_process_mock()
        with patch.object(
                subprocess, 'Popen', return_value=process_mock) as popen_mock:
            exec_cmd(cmd)

        popen_mock.assert_called_once_with(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True)

    @mock.patch('fuel_upgrade.utils.exec_cmd',
                side_effect=errors.ExecutedErrorNonZeroExitCode())
    def test_safe_exec_cmd(self, exec_mock):
        cmd = 'some command'
        utils.safe_exec_cmd(cmd)
        exec_mock.assert_called_once_with(cmd)

    def test_exec_cmd_raises_error_in_case_of_non_zero_exit_code(self):
        cmd = 'some command'
        return_code = 1

        process_mock = self.make_process_mock(return_code=return_code)
        with patch.object(subprocess, 'Popen', return_value=process_mock):
            self.assertRaisesRegexp(
                errors.ExecutedErrorNonZeroExitCode,
                'Shell command executed with "{0}" '
                'exit code: {1} '.format(return_code, cmd),
                exec_cmd, cmd)

    def test_exec_cmd_iterator_executes_sucessfuly(self):
        cmd = 'some command'

        process_mock = self.make_process_mock()
        with patch.object(
                subprocess, 'Popen', return_value=process_mock) as popen_mock:
            for line in exec_cmd_iterator(cmd):
                self.assertTrue(line.startswith('Stdout line '))

        popen_mock.assert_called_once_with(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True)

    def test_exec_cmd_iterator_raises_error_in_case_of_non_zero_exit_code(
            self):
        cmd = 'some command'
        return_code = 1

        process_mock = self.make_process_mock(return_code=return_code)
        with patch.object(subprocess, 'Popen', return_value=process_mock):
            with self.assertRaisesRegexp(
                    errors.ExecutedErrorNonZeroExitCode,
                    'Shell command executed with "{0}" '
                    'exit code: {1} '.format(return_code, cmd)):
                for line in exec_cmd_iterator(cmd):
                    self.assertTrue(line.startswith('Stdout line '))

    def test_get_request(self):
        url = 'http://some-url.com/path'
        response = mock.MagicMock()
        response.read.return_value = '{"key": "value"}'
        response.getcode.return_value = 200

        with patch.object(
                urllib2, 'urlopen', return_value=response) as urlopen:

            resp = get_request(url)
            self.assertEqual(({'key': 'value'}, 200), resp)

        urlopen.assert_called_once_with(url)

    def test_topological_sorting(self):
        graph = {
            'D': ['C', 'G'],
            'E': ['A', 'D'],
            'A': [],
            'B': ['A'],
            'C': ['A'],
            'G': []
        }

        order = topological_sorting(graph)
        self.assertEqual(order, ['A', 'B', 'C', 'G', 'D', 'E'])

    def test_topological_sorting_raises_cycle_dependencies_error(self):
        graph = {
            'A': ['C', 'D'],
            'B': ['A'],
            'C': ['B'],
            'D': []
        }

        self.assertRaisesRegexp(
            errors.CyclicDependenciesError,
            "Cyclic dependencies error ",
            topological_sorting,
            graph)

    @mock.patch('fuel_upgrade.utils.os.makedirs')
    def test_create_dir_if_not_exists_does_not_create_dir(self, mock_makedirs):
        path = 'some_path'

        with mock.patch(
                'fuel_upgrade.utils.os.path.isdir',
                return_value=True) as mock_isdir:

            create_dir_if_not_exists(path)
            mock_isdir.assert_called_once_with(path)
            self.method_was_not_called(mock_makedirs)

    @mock.patch('fuel_upgrade.utils.os.makedirs')
    def test_create_dir_if_not_exists(self, mock_makedirs):
        path = 'some_path'
        with mock.patch(
                'fuel_upgrade.utils.os.path.isdir',
                return_value=False) as mock_isdir:

            create_dir_if_not_exists(path)
            mock_isdir.assert_called_once_with(path)
            mock_makedirs.assert_called_once_with(path)

    def test_wait_for_true_does_not_raise_errors(self):
        self.assertEqual(wait_for_true(lambda: True, timeout=0), True)

    def test_wait_for_true_raises_timeout_error(self):
        self.assertRaisesRegexp(
            errors.TimeoutError,
            'Failed to execute command with timeout 0',
            wait_for_true,
            lambda: False,
            timeout=0)

    @mock.patch('fuel_upgrade.utils.os.path.isdir', return_value=True)
    @mock.patch('fuel_upgrade.utils.copy_dir')
    def test_copy_with_dir(self, copy_mock, _):
        from_path = '/from_path'
        to_path = '/to_path'

        utils.copy(from_path, to_path)
        copy_mock.assert_called_once_with(from_path, to_path, True, True)

    @mock.patch('fuel_upgrade.utils.os.path.isdir', return_value=False)
    @mock.patch('fuel_upgrade.utils.copy_file')
    def test_copy_with_file(self, copy_mock, _):
        from_path = '/from_path'
        to_path = '/to_path'

        utils.copy(from_path, to_path)
        copy_mock.assert_called_once_with(from_path, to_path, True)

    @mock.patch('fuel_upgrade.utils.os.path.isdir', return_value=False)
    @mock.patch('fuel_upgrade.utils.shutil.copy')
    def test_copy_file(self, copy_mock, _):
        from_path = '/from_path.txt'
        to_path = '/to_path.txt'

        utils.copy_file(from_path, to_path)
        copy_mock.assert_called_once_with(from_path, to_path)

    @mock.patch('fuel_upgrade.utils.os.path.isdir', return_value=True)
    @mock.patch('fuel_upgrade.utils.shutil.copy')
    def test_copy_file_to_dir(self, copy_mock, _):
        from_path = '/from_path.txt'
        to_path = '/to_path'

        utils.copy_file(from_path, to_path)
        copy_mock.assert_called_once_with(from_path, '/to_path/from_path.txt')

    @mock.patch('fuel_upgrade.utils.os.path.isdir', return_value=False)
    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=True)
    @mock.patch('fuel_upgrade.utils.shutil.copy')
    def test_copy_file_do_not_overwrite(self, copy_mock, _, __):
        from_path = '/from_path.txt'
        to_path = '/to_path.txt'

        utils.copy_file(from_path, to_path, overwrite=False)
        self.method_was_not_called(copy_mock)

    @mock.patch('fuel_upgrade.utils.shutil.copytree')
    def test_copy_dir(self, copy_mock):
        from_path = '/from_path'
        to_path = '/to_path'

        utils.copy_dir(from_path, to_path)
        copy_mock.assert_called_once_with(from_path, to_path, symlinks=True)

    @mock.patch('fuel_upgrade.utils.os.path.lexists', return_value=True)
    @mock.patch('fuel_upgrade.utils.shutil.copytree')
    @mock.patch('fuel_upgrade.utils.remove')
    def test_copy_dir_overwrite(self, rm_mock, copy_mock, _):
        from_path = '/from_path'
        to_path = '/to_path'

        utils.copy_dir(from_path, to_path)
        rm_mock.assert_called_once_with(to_path, ignore_errors=True)
        copy_mock.assert_called_once_with(from_path, to_path, symlinks=True)

    def test_file_contains_lines_returns_true(self):
        with mock.patch(
                '__builtin__.open',
                self.mock_open("line 1\n line2\n line3")):

            self.assertTrue(
                utils.file_contains_lines('/some/path', ['line 1', 'line3']))

    def test_file_contains_lines_returns_false(self):
        with mock.patch(
                '__builtin__.open',
                self.mock_open("line 1\n line2\n line3")):

            self.assertFalse(
                utils.file_contains_lines('/some/path', ['line 4', 'line3']))

    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=True)
    @mock.patch('fuel_upgrade.utils.os.symlink')
    @mock.patch('fuel_upgrade.utils.remove')
    def test_symlink(self, remove_mock, symlink_mock, _):
        from_path = '/tmp/from/path'
        to_path = '/tmp/to/path'
        utils.symlink(from_path, to_path)

        symlink_mock.assert_called_once_with(from_path, to_path)
        remove_mock.assert_called_once_with(to_path)

    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=False)
    @mock.patch('fuel_upgrade.utils.os.symlink')
    @mock.patch('fuel_upgrade.utils.remove')
    def test_symlink_no_exist(self, remove_mock, symlink_mock, _):
        from_path = '/tmp/from/path'
        to_path = '/tmp/to/path'
        utils.symlink(from_path, to_path)

        symlink_mock.assert_called_once_with(from_path, to_path)
        self.called_once(remove_mock)

    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=True)
    @mock.patch('fuel_upgrade.utils.os.remove')
    def test_remove_if_exists(self, remove_mock, exists_mock):
        path = '/tmp/some/path'
        utils.remove_if_exists(path)
        remove_mock.assert_called_once_with(path)
        exists_mock.assert_called_once_with(path)

    def test_load_fixture(self):
        fixture = StringIO.StringIO('''
        - &base
          fields:
            a: 1
            b: 2
            c: 3

        - pk: 1
          extend: *base
          fields:
            a: 13

        - pk: 2
          extend: *base
          fields:
            d: 42
        ''')
        setattr(fixture, 'name', 'some.yaml')

        result = utils.load_fixture(fixture)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {
            'a': 13,
            'b': 2,
            'c': 3,
        })
        self.assertEqual(result[1], {
            'a': 1,
            'b': 2,
            'c': 3,
            'd': 42,
        })

    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=True)
    @mock.patch('fuel_upgrade.utils.shutil.rmtree')
    def test_rmtree(self, rm_mock, exists_mock):
        path = '/some/file/path'
        utils.rmtree(path)
        rm_mock.assert_called_once_with(path, ignore_errors=True)
        exists_mock.assert_called_once_with(path)

    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=False)
    @mock.patch('fuel_upgrade.utils.shutil.rmtree')
    def test_rmtree_no_errors_if_file_does_not_exist(
            self, rm_mock, exists_mock):

        path = '/some/file/path'
        utils.rmtree(path)

        self.method_was_not_called(rm_mock)
        exists_mock.assert_called_once_with(path)

    def test_check_file_is_valid_json(self):
        path = '/path/to/file.json'
        with mock.patch(
                '__builtin__.open',
                self.mock_open('{"valid": "json"}')):
            self.assertTrue(utils.check_file_is_valid_json(path))

    def test_check_file_is_valid_json_returns_false(self):
        path = '/path/to/file.json'
        with mock.patch(
                '__builtin__.open',
                self.mock_open('{"invalid: "json"}')):
            self.assertFalse(utils.check_file_is_valid_json(path))

    def test_check_file_is_valid_json_false_if_problems_with_access(self):
        path = '/path/to/file.json'
        with mock.patch('__builtin__.open', side_effect=IOError()):
            self.assertFalse(utils.check_file_is_valid_json(path))

    def test_byte_to_megabyte(self):
        self.assertEqual(utils.byte_to_megabyte(0), 0)
        self.assertEqual(utils.byte_to_megabyte(1048576), 1)

    def test_calculate_free_space(self):
        dev_info = mock.Mock()
        dev_info.f_bsize = 1048576
        dev_info.f_bavail = 2
        with mock.patch('fuel_upgrade.utils.os.statvfs',
                        return_value=dev_info) as st_mock:
            self.assertEqual(utils.calculate_free_space('/tmp/dir'), 2)

        st_mock.assert_called_once_with('/tmp/dir/')

    @mock.patch('fuel_upgrade.utils.os.path.ismount',
                side_effect=[False, False, True])
    def test_find_mount_point(self, mock_ismount):
        path = '/dir1/dir2/dir3/dir4'
        self.assertEqual(utils.find_mount_point(path), '/dir1/dir2')
        self.called_times(mock_ismount, 3)

    @mock.patch('fuel_upgrade.utils.os.path.getsize', return_value=1048576)
    @mock.patch('fuel_upgrade.utils.os.walk',
                return_value=[('', '', ['file1', 'file2'])])
    @mock.patch('fuel_upgrade.utils.os.path.isfile',
                return_value=True)
    def test_dir_size(self, _, __, ___):
        path = '/path/dir'
        self.assertEqual(utils.dir_size(path), 2)

    @mock.patch('fuel_upgrade.utils.os.path.getsize', return_value=1048576)
    @mock.patch('fuel_upgrade.utils.os.path.isfile', return_value=True)
    def test_files_size(self, _, __):
        path = ['/path/file1', '/path/file2']
        self.assertEqual(utils.files_size(path), 2)

    def test_compare_version(self):
        self.assertEqual(utils.compare_version('0.1', '0.2'), 1)
        self.assertEqual(utils.compare_version('0.1', '0.1.5'), 1)
        self.assertEqual(utils.compare_version('0.2', '0.1'), -1)
        self.assertEqual(utils.compare_version('0.2', '0.2'), 0)

    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=True)
    @mock.patch('fuel_upgrade.utils.copy')
    def test_copy_if_does_not_exist_file_exists(self, copy_mock, exists_mock):
        utils.copy_if_does_not_exist('from', 'to')
        exists_mock.assert_called_once_with('to')
        self.method_was_not_called(copy_mock)

    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=False)
    @mock.patch('fuel_upgrade.utils.copy')
    def test_copy_if_does_not_exist_file_does_not_exist(
            self, copy_mock, exists_mock):
        utils.copy_if_does_not_exist('from', 'to')
        exists_mock.assert_called_once_with('to')
        copy_mock.assert_called_once_with('from', 'to')

    @mock.patch('fuel_upgrade.utils.os.rename')
    def test_rename(self, rename_mock):
        utils.rename('source', 'destination')
        rename_mock.assert_called_once_with('source', 'destination')

    @mock.patch('fuel_upgrade.utils.os.path.lexists', return_value=True)
    @mock.patch('fuel_upgrade.utils.os.path.isdir', return_value=False)
    @mock.patch('fuel_upgrade.utils.os.remove')
    def test_remove_file(self, remove_mock, _, __):
        utils.remove('path')
        remove_mock.assert_called_once_with('path')

    @mock.patch('fuel_upgrade.utils.os.path.lexists', return_value=True)
    @mock.patch('fuel_upgrade.utils.os.path.islink', return_value=True)
    @mock.patch('fuel_upgrade.utils.os.path.isdir', return_value=True)
    @mock.patch('fuel_upgrade.utils.os.remove')
    def test_remove_link_to_dir(self, remove_mock, _, __, ___):
        utils.remove('path')
        remove_mock.assert_called_once_with('path')

    @mock.patch('fuel_upgrade.utils.os.path.lexists', return_value=False)
    @mock.patch('fuel_upgrade.utils.os.path.isdir', return_value=False)
    @mock.patch('fuel_upgrade.utils.os.remove')
    def test_remove_file_does_not_exist(self, remove_mock, _, __):
        utils.remove('path')
        self.method_was_not_called(remove_mock)

    @mock.patch('fuel_upgrade.utils.os.path.lexists', return_value=True)
    @mock.patch('fuel_upgrade.utils.os.path.isdir', return_value=True)
    @mock.patch('fuel_upgrade.utils.shutil.rmtree')
    def test_remove_dir(self, remove_mock, _, __):
        utils.remove('path')
        remove_mock.assert_called_once_with('path', ignore_errors=True)

    @mock.patch('fuel_upgrade.utils.yaml')
    def test_save_as_yaml(self, yaml_mock):
        path = '/tmp/path'
        data = {'a': 'b'}
        mock_open = self.mock_open('')
        with mock.patch('__builtin__.open', mock_open):
            utils.save_as_yaml(path, data)

        yaml_mock.dump.assert_called_once_with(data, default_flow_style=False)

    def test_generate_uuid_string(self):
        random_string = utils.generate_uuid_string()
        self.assertEqual(len(random_string), 36)
        self.assertTrue(isinstance(random_string, str))

    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=True)
    @mock.patch('fuel_upgrade.utils.file_contains_lines', returns_value=True)
    def test_verify_postgres_dump(self, file_contains_mock, exists_mock):
        pg_dump_path = '/tmp/some/path'
        utils.verify_postgres_dump(pg_dump_path)

        patterns = [
            '-- PostgreSQL database cluster dump',
            '-- PostgreSQL database dump',
            '-- PostgreSQL database dump complete',
            '-- PostgreSQL database cluster dump complete']

        exists_mock.assert_called_once_with(pg_dump_path)
        file_contains_mock.assert_called_once_with(pg_dump_path, patterns)

    def test_file_extension(self):
        cases = [
            ('', ''),
            ('asdf', ''),
            ('asdf.', ''),
            ('asdf.txt', 'txt'),
            ('asdf.txt.trtr', 'trtr')]

        for case in cases:
            self.assertEqual(utils.file_extension(case[0]), case[1])

    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=True)
    def test_file_exists_returns_true(self, exists_mock):
        self.assertTrue(utils.file_exists('path'))
        exists_mock.assert_called_once_with('path')

    @mock.patch('fuel_upgrade.utils.os.path.exists', return_value=False)
    def test_file_exists_returns_false(self, exists_mock):
        self.assertFalse(utils.file_exists('path'))
        exists_mock.assert_called_once_with('path')

    @mock.patch('fuel_upgrade.utils.os.walk')
    def test_iterfiles(self, walk):
        for _ in utils.iterfiles('path/to/dir'):
            pass
        walk.assert_called_once_with('path/to/dir', topdown=True)


class TestVersionedFile(BaseTestCase):

    def setUp(self):
        self.path = '/tmp/path.ext'
        self.versioned_file = utils.VersionedFile(self.path)

    @mock.patch('fuel_upgrade.utils.glob.glob', return_value=[])
    def test_next_file_name_empty_dir(self, _):
        self.assertEqual(
            self.versioned_file.next_file_name(),
            '{0}.1'.format(self.path))

    @mock.patch('fuel_upgrade.utils.glob.glob',
                return_value=['/tmp/path.ext',
                              '/tmp/path.ext.10',
                              '/tmp/path.ext.6'])
    def test_next_file_name_with_files(self, _):
        self.assertEqual(
            self.versioned_file.next_file_name(),
            '{0}.11'.format(self.path))

    @mock.patch('fuel_upgrade.utils.glob.glob',
                return_value=['/tmp/path.ext',
                              '/tmp/path.ext.10',
                              '/tmp/path.ext.6'])
    def test_sorted_files(self, _):
        self.assertEqual(
            self.versioned_file.sorted_files(),
            ['/tmp/path.ext.10', '/tmp/path.ext.6'])
