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

import os

import mock
import yaml

from tasklib import config
from tasklib import exceptions
from tasklib import task
from tasklib.tests import base


@mock.patch('tasklib.task.os.path.exists')
class TestBaseTask(base.BaseUnitTest):
    """Basic task tests."""

    def setUp(self):
        self.conf = config.Config()

    def test_create_task_from_path(self, mexists):
        name = 'ceph/deploy'
        task_dir = os.path.join(self.conf['library_dir'], name)
        test_task = task.Task.task_from_dir(task_dir, self.conf)
        self.assertEqual(test_task.name, name)
        self.assertEqual(test_task.dir, task_dir)

    def test_verify_raises_not_found(self, mexists):
        mexists.return_value = False
        test_task = task.Task('ceph/deploy', self.conf)
        self.assertRaises(exceptions.NotFound, test_task.verify)

    def test_verify_nothing_happens_if_file_exists(self, mexists):
        mexists.return_value = True
        test_task = task.Task('ceph/deploy', self.conf)
        test_task.verify()

    def test_read_metadata_from_valid_yaml(self, mexists):
        mexists.return_value = True
        meta = {'report_dir': '/tmp/report_dir',
                'pid_dir': '/tmp/pid_dir'}
        mopen = mock.mock_open(read_data=yaml.dump(meta))
        test_task = task.Task('ceph/deploy', self.conf)
        with mock.patch('tasklib.task.open', mopen, create=True):
            self.assertEqual(meta, test_task.metadata)
