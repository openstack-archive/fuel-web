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


CEPH_TASKS = {'ceph': [{'description': 'Install ceph osd',
                        'name': 'install_ceph',
                        'priority': 20}],
              'controller': [{'description': 'Install ceph mon',
                              'name': 'install_ceph_mon',
                              'priority': 10}]}

MONGO_TASKS = {'mongo': [{'description': 'Install mongo db',
                         'name': 'install_mongo',
                         'priority': 20}]}

BASE_TASKS = {'controller': [{'description': 'Install all the stuff',
                              'name': 'deploy_puppet',
                              'priority': 1}],
              'compute': [{'description': 'Install all the stuff on compute',
                           'name': 'deploy_puppet_compute',
                           'priority': 1}]}

VCENTER_TASKS = {'controller': [{'description': 'Install vcenter driver',
                                 'name': 'install_vcenter_driver',
                                 'priority': 20,
                                 'condition': 'false'}]}

XEN_TASKS = {'compute': [{'description': 'Install xen stuff on compute',
                          'name': 'deploy_xen_driver',
                          'priority': 20,
                          'condition': 'true'}]}

content_map = {
    'mongo': MONGO_TASKS,
    'ceph': CEPH_TASKS,
    'base': BASE_TASKS,
    'vcenter': VCENTER_TASKS,
    'xen': XEN_TASKS
}


def get_config(file_name):
    for pattern, content in content_map.iteritems():
        if pattern in file_name:
            return mock.mock_open(read_data=yaml.dump(content))()


@mock.patch('nailgun.objects.cluster.glob.glob')
@mock.patch('__builtin__.open', mock.MagicMock(side_effect=get_config))
class TestReleaseGetTaskMetadata(base.BaseTestCase):

    def setUp(self):
        super(TestReleaseGetTaskMetadata, self).setUp()
        self.env.create()
        self.cluster = self.env.clusters[0]

    def test_get_non_conditional_tasks(self, mglob):
        mglob.return_value = ['/etc/fuel/tasks/2014.1.1-5.1/ceph.yaml',
                              '/etc/fuel/tasks/2014.1.1-5.1/mongo.yaml']
        glob_pattern = os.path.join(
            settings.TASK_DIR, self.cluster.release.version, '*.yaml')
        task_metadata = objects.Cluster.get_cluster_tasks(self.cluster)
        mglob.assert_called_once_with(glob_pattern)
        self.assertEqual(task_metadata['mongo'], MONGO_TASKS['mongo'])
        self.assertEqual(task_metadata['ceph'], CEPH_TASKS['ceph'])
        self.assertEqual(task_metadata['controller'], CEPH_TASKS['controller'])

    def test_get_tasks_for_cluster(self, mglob):
        mglob.return_value = ['/etc/fuel/tasks/2014.1.1-5.1/base.yaml',
                              '/etc/fuel/tasks/2014.1.1-5.1/vcenter.yaml',
                              '/etc/fuel/tasks/2014.1.1-5.1/xen.yaml']
        glob_pattern = os.path.join(
            settings.TASK_DIR, self.cluster.release.version, '*.yaml')
        task_metadata = objects.Cluster.get_cluster_tasks(self.cluster)
        mglob.assert_called_once_with(glob_pattern)
        self.assertEqual(len(task_metadata['controller']), 1)
        self.assertEqual(len(task_metadata['compute']), 2)
        self.assertEqual(task_metadata['controller'], BASE_TASKS['controller'])
        self.assertEqual(
            task_metadata['compute'],
            BASE_TASKS['compute'] + XEN_TASKS['compute'])
