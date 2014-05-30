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

import subprocess
import urllib2

import mock
from mock import patch

from fuel_upgrade import errors
from fuel_upgrade.tests.base import BaseTestCase
from fuel_upgrade.utils import create_dir_if_not_exists
from fuel_upgrade.utils import exec_cmd
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

    def test_get_request(self):
        url = 'http://some-url.com/path'
        response = mock.MagicMock()
        response.read.return_value = '{"key": "value"}'
        response.read.getcode = 200

        with patch.object(
                urllib2, 'urlopen', return_value=response) as urlopen:

            json_resp = get_request(url)
            self.assertEquals({'key': 'value'}, json_resp)

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
        self.assertEquals(order, ['A', 'C', 'B', 'G', 'D', 'E'])

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
            mock_makedirs.called_once(path)

    def test_wait_for_true_does_not_raise_errors(self):
        self.assertEquals(wait_for_true(lambda: True, timeout=0), True)

    def test_wait_for_true_raises_timeout_error(self):
        self.assertRaisesRegexp(
            errors.TimeoutError,
            'Failed to execute command with timeout 0',
            wait_for_true,
            lambda: False,
            timeout=0)
