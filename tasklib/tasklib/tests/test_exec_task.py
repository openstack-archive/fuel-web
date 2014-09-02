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
import yaml

from tasklib import config
from tasklib import task
from tasklib.tests import base


@mock.patch('tasklib.task.os.path.exists')
@mock.patch('tasklib.utils.execute')
class TestExecTask(base.BaseUnitTest):

    def setUp(self):
        self.meta = {'cmd': 'echo 1',
                     'type': 'exec'}
        self.only_required = {'type': 'puppet'}
        self.config = config.Config()

    def test_base_cmd_task(self, mexecute, mexists):
        mexists.return_value = True
        mexecute.return_value = (0, '', '')
        mopen = mock.mock_open(read_data=yaml.dump(self.meta))
        puppet_task = task.Task('test/cmd', self.config)
        with mock.patch('tasklib.task.open', mopen, create=True):
            puppet_task.run()
        expected_cmd = 'echo 1'
        mexecute.assert_called_once_with(expected_cmd)
