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

from tasklib import config
from tasklib import task
from tasklib.tests import base

task_file_yaml = '''comment: A test task
description: A task used to test exec action
cmd: echo 1
type: exec
'''


@mock.patch('tasklib.utils.execute')
@mock.patch.object(task.Task, 'change_directory_back',
                   return_value=True)
@mock.patch.object(task.Task, 'change_directory_to_task',
                   return_value=True)
@mock.patch.object(task.Task, 'read_task_file',
                   return_value=task_file_yaml)
@mock.patch.object(task.Task, 'verify',
                   return_value=True)
class TestExecTask(base.BaseUnitTest):

    def setUp(self):
        self.config = config.Config()

    def test_task_exec_cmd(self, m_verify, m_read, m_cd_task, m_cd_back,
                           m_execute):
        m_execute.return_value = (0, '', '')
        exec_task = task.Task('test/cmd', self.config)
        exec_task.run()
        expected_cmd = 'echo 1'
        m_execute.assert_called_once_with(expected_cmd)

    def test_task_exec_chdir(self, m_verify, m_read, m_cd_task, m_cd_back,
                             m_execute):
        m_execute.return_value = (0, '', '')
        exec_task = task.Task('test/cmd', self.config)
        exec_task.run()
        m_cd_task.assert_called_once_with()
        self.assertTrue(m_execute.called)
        m_cd_back.assert_called_once_with()
