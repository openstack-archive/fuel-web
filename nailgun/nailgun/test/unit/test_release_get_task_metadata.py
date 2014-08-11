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

from nailgun import objects
from nailgun.settings import settings
from nailgun.test import base


TASK_CONFIGS = ['/etc/fuel/tasks/2014.1.1-5.1/ceph.yaml',
                '/etc/fuel/tasks/2014.1.1-5.1/mongo.yaml']

CEPH_TASKS = {'ceph': [{'description': 'Install ceph osd',
                        'name': 'install_ceph',
                        'priority': 20}],
              'controller': [{'description': 'Install ceph mon',
                              'name': 'install_ceph_mon',
                              'priority': 10}]}

MONGO_TASKS = {'mongo': [{'description': 'Install mongo db',
                         'name': 'install_mongo',
                         'priority': 20}]}


def get_config(file_name):
    if 'mongo' in file_name:
        return mock.mock_open(read_data=yaml.dump(MONGO_TASKS))()
    elif 'ceph' in file_name:
        return mock.mock_open(read_data=yaml.dump(CEPH_TASKS))()

access_mock = mock.MagicMock(side_effect=get_config)


@mock.patch('nailgun.objects.release.glob.glob')
class TestReleaseGetTaskMetadata(base.BaseTestCase):

    def setUp(self):
        super(TestReleaseGetTaskMetadata, self).setUp()
        self.release = self.env.create_release()

    def test_get_task_metadata(self, mglob):
        mglob.return_value = TASK_CONFIGS
        glob_pattern = os.path.join(
            settings.TASK_DIR, self.release.version, '*.yaml')
        mglob.assert_called_once_with(glob_pattern)
        with mock.patch('__builtin__.open', access_mock):
            task_metadata = objects.Release.get_task_metadata(
                self.release, settings.TASK_DIR)
        self.assertEqual(task_metadata['mongo'], MONGO_TASKS['mongo'])
        self.assertEqual(task_metadata['ceph'], CEPH_TASKS['ceph'])
        self.assertEqual(task_metadata['controller'], CEPH_TASKS['controller'])
