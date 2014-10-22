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

from tasklib.actions.puppet import PuppetAction
from tasklib import config
from tasklib import task
from tasklib.tests import base

task_file_yaml = '''comment: A test Puppet task
description: A task used to test Puppet action
type: puppet
puppet_modules: /etc/my_puppet_modules
puppet_manifest: init.pp
'''

task_file_only_required = 'type: puppet'


@mock.patch.object(PuppetAction, 'all_success_criterias',
                   return_value={'mock': True})
@mock.patch.object(task.Task, 'change_directory_back',
                   return_value=True)
@mock.patch.object(task.Task, 'change_directory_to_task',
                   return_value=True)
@mock.patch.object(task.Task, 'read_task_file')
@mock.patch('tasklib.task.os.path.exists')
@mock.patch('tasklib.utils.execute')
class TestPuppetTask(base.BaseUnitTest):

    def setUp(self):
        self.only_required = {'type': 'puppet'}
        self.config = config.Config()

    def test_basic_puppet_action(self, mexecute, mexists, mread, m_cd_task,
                                 m_cd_back, m_success):
        mexists.return_value = True
        mexecute.return_value = (0, '', '')
        mread.return_value = task_file_yaml
        puppet_task = task.Task('test/puppet', self.config)
        puppet_task.run()
        expected_cmd = [
            'puppet', 'apply',
            '--detailed-exitcodes',
            '--modulepath=/etc/my_puppet_modules',
            '--logdest syslog',
            '--logdest /var/log/puppet.log',
            '--logdest console',
            '--report',
            '--debug',
            '--verbose',
            '--evaltrace',
            '--trace',
            '/etc/puppet/tasks/test/puppet/init.pp'
        ]
        expected = ' '.join(expected_cmd)
        self.assertEqual(mexecute.call_count, 1)
        received = mexecute.call_args[0][0]
        self.assertTrue(expected in received)

    def test_default_puppet_action(self, mexecute, mexists, mread, m_cd_task,
                                   m_cd_back, m_success):
        mexists.return_value = True
        mexecute.return_value = (0, '', '')
        mread.return_value = task_file_only_required
        puppet_task = task.Task('test/puppet/only_required', self.config)
        puppet_task.run()
        expected_cmd = [
            'puppet', 'apply', '--detailed-exitcodes',
            '--modulepath={0}'.format(self.config['puppet_modules'])]
        expected = ' '.join(expected_cmd)
        self.assertEqual(mexecute.call_count, 1)
        received = mexecute.call_args[0][0]
        self.assertTrue(expected in received)
