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
from fuel_upgrade.utils import exec_cmd
from fuel_upgrade.utils import get_request


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
