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

import mock

from tasklib import cli
from tasklib.tests import base


class TestCmdApi(base.BaseUnitTest):

    def setUp(self):
        self.api = cli.CmdApi()
        self.api.config['log_file'] = None

    @mock.patch('tasklib.cli.task.Task.task_from_dir')
    @mock.patch('tasklib.cli.utils.find_all_tasks')
    def test_list(self, mfind, mtask):
        tasks = ['/etc/library/test/deploy', '/etc/library/test/rollback']
        mfind.return_value = tasks
        self.api.parse(['list'])
        mfind.assert_called_once_with(self.api.config)
        expected_calls = []
        for t in tasks:
            expected_calls.append(mock.call(t, self.api.config))
        self.assertEqual(expected_calls, mtask.call_args_list)
