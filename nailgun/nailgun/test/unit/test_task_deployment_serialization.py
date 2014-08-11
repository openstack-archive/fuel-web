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

from collections import defaultdict

import mock

from nailgun.orchestrator import deployment_serializers
from nailgun.settings import settings
from nailgun.test import base


TASKS = {'compute': [{'description': 'Do some stuff on node',
                      'name': 'compute_stuff',
                      'priority': 0}],
         'primary-controller': [{'description': 'Do some stuff on node',
                                 'name': 'stuff',
                                 'priority': 0},
                                {'description': 'Do other stuff',
                                 'name': 'other_stuff',
                                 'priority': 10}]}


@mock.patch('nailgun.orchestrator.deployment_serializers.objects.Release.'
            'get_task_metadata')
class TestTaskDeploymentSerializer(base.BaseTestCase):

    def setUp(self):
        super(TestTaskDeploymentSerializer, self).setUp()
        node_args = [
            {'roles': ['controller'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True}]
        self.env.create(nodes_kwargs=node_args)
        self.cluster = self.env.clusters[0]
        self.nodes = self.cluster.nodes
        self.tasks = defaultdict(list)
        self.tasks.update(TASKS)

    def test_task_serializer_tasks_present(self, task_metadata_mock):
        task_metadata_mock.return_value = self.tasks
        serialized_nodes = deployment_serializers.serialize(
            self.cluster, self.nodes)
        task_metadata_mock.assert_called_once_with(
            self.cluster.release, settings.TASK_DIR)
        for node in serialized_nodes:
            self.assertEqual(node['tasks'], self.tasks[node['role']])

    def test_task_serializer_tasks_not_present(self, task_metadata_mock):
        task_metadata_mock.return_value = defaultdict(list)
        serialized_nodes = deployment_serializers.serialize(
            self.cluster, self.nodes)
        task_metadata_mock.assert_called_once_with(
            self.cluster.release, settings.TASK_DIR)
        for node in serialized_nodes:
            self.assertNotIn('tasks', node)


@mock.patch('nailgun.orchestrator.deployment_serializers.objects.Release.'
            'get_task_metadata')
class TestTaskDeploymentNotAllPresent(base.BaseTestCase):

    def setup_env(self, node_args):
        self.env.create(nodes_kwargs=node_args)
        self.cluster = self.env.clusters[0]
        self.nodes = self.cluster.nodes
        self.tasks = defaultdict(list)
        self.tasks.update(TASKS)

    def test_serialize_non_existent_nodes(self, task_metadata_mock):
        self.setup_env([
            {'roles': ['cinder'], 'pending_addition': True},
            {'roles': ['ceph'], 'pending_addition': True}])
        task_metadata_mock.return_value = self.tasks
        serialized_nodes = deployment_serializers.serialize(
            self.cluster, self.nodes)
        task_metadata_mock.assert_called_once_with(
            self.cluster.release, settings.TASK_DIR)
        for node in serialized_nodes:
            self.assertEqual(node['tasks'], [])

    def test_serialize_primary_and_non(self, task_metadata_mock):
        self.setup_env([
            {'roles': ['controller'], 'pending_addition': True},
            {'roles': ['controller'], 'pending_addition': True}])
        task_metadata_mock.return_value = self.tasks
        serialized_nodes = deployment_serializers.serialize(
            self.cluster, self.nodes)
        task_metadata_mock.assert_called_once_with(
            self.cluster.release, settings.TASK_DIR)
        for node in serialized_nodes:
            if node['role'] == 'primary-controller':
                self.assertEqual(node['tasks'], TASKS[node['role']])
            elif node['role'] == 'controller':
                self.assertEqual(node['tasks'], [])
