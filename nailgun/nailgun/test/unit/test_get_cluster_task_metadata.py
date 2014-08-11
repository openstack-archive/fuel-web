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


CEPH_TASKS = [{
    'description': 'Install ceph osd',
    'type': 'shell',
    'role': ['compute', 'controller'],
    'parameters': {'cmd': 'echo 1'}}]

MONGO_TASKS = [{
    'description': 'Install mongo db',
    'type': 'shell',
    'role': ['compute', 'controller'],
    'parameters': {'cmd': 'echo 11'}}]

BASE_TASKS = [{
    'description': 'Install basic stuff',
    'type': 'puppet',
    'role': ['compute', 'controller', 'cinder'],
    'parameters': {'puppet_manifests': 'site.pp',
                   'puppet_modules': '/etc/modules'}}]


content_map = {
    'mongo': MONGO_TASKS,
    'ceph': CEPH_TASKS,
    'base': BASE_TASKS,
}


def get_config(file_name):
    for pattern, content in content_map.iteritems():
        if pattern in file_name:
            return mock.mock_open(read_data=yaml.dump(content))()


@mock.patch('nailgun.objects.cluster.glob.glob')
@mock.patch('nailgun.objects.cluster.open',
            mock.MagicMock(side_effect=get_config),
            create=True)
class TestGetTaskMetadata(base.BaseTestCase):

    def setUp(self):
        super(TestGetTaskMetadata, self).setUp()
        self.env.create()
        self.cluster = self.env.clusters[0]

    def test_get_non_conditional_tasks(self, mglob):
        mglob.return_value = ['2014.1.1-5.1/ceph.yaml',
                              '2014.1.1-5.1/mongo.yaml']
        glob_pattern = os.path.join(
            settings.TASK_DIR.format(
                RELEASE_VERSION=self.cluster.release.version),
            '*.yaml')
        task_metadata = objects.Cluster.get_tasks(self.cluster)
        mglob.assert_called_once_with(glob_pattern)
        self.assertEqual(task_metadata, CEPH_TASKS + MONGO_TASKS)

    def test_get_tasks_for_cluster(self, mglob):
        mglob.return_value = ['2014.1.1-5.1/base.yaml',
                              '2014.1.1-5.1/ceph.yaml',
                              '2014.1.1-5.1/mongo.yaml']
        glob_pattern = os.path.join(
            settings.TASK_DIR.format(
                RELEASE_VERSION=self.cluster.release.version),
            '*.yaml')
        task_metadata = objects.Cluster.get_tasks(self.cluster)
        mglob.assert_called_once_with(glob_pattern)
        self.assertEqual(task_metadata, BASE_TASKS + CEPH_TASKS + MONGO_TASKS)
