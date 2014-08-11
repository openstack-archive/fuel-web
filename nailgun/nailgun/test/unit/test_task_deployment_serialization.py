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

from nailgun.orchestrator import deployment_serializers
from nailgun.test import base


TASKS = [{'description': 'Do some stuff on node',
          'role': ['controller', 'compute', 'primary-controller'],
          'type': 'shell',
          'parameters': {
              'cmd': 'echo 123',
              'timeout': 120}},
         {'description': 'Do other stuff',
          'type': 'shell',
          'role': ['controller', 'compute', 'primary-controller'],
          'parameters': {
              'cmd': 'echo 1234',
              'timeout': 120}}]


@mock.patch('nailgun.orchestrator.deployment_serializers.objects.Cluster.'
            'get_tasks')
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

    def test_task_serializer_tasks_present(self, task_metadata_mock):
        task_metadata_mock.return_value = TASKS
        serialized_nodes = deployment_serializers.serialize(
            self.cluster, self.nodes)
        task_metadata_mock.assert_called_once_with(self.cluster)
        for node in serialized_nodes:
            self.assertEqual(len(node['tasks']), 2)

    def test_task_serializer_tasks_not_present(self, task_metadata_mock):
        task_metadata_mock.return_value = []
        serialized_nodes = deployment_serializers.serialize(
            self.cluster, self.nodes)
        task_metadata_mock.assert_called_once_with(self.cluster)
        for node in serialized_nodes:
            self.assertEqual([], node['tasks'])


@mock.patch('nailgun.orchestrator.deployment_serializers.objects.Cluster.'
            'get_tasks')
class TestTaskDeploymentNotAllPresent(base.BaseTestCase):

    def setup_env(self, node_args):
        self.env.create(nodes_kwargs=node_args)
        self.cluster = self.env.clusters[0]
        self.nodes = self.cluster.nodes

    def test_serialize_non_existent_nodes(self, task_metadata_mock):
        self.setup_env([
            {'roles': ['cinder'], 'pending_addition': True},
            {'roles': ['ceph'], 'pending_addition': True}])
        task_metadata_mock.return_value = TASKS
        serialized_nodes = deployment_serializers.serialize(
            self.cluster, self.nodes)
        task_metadata_mock.assert_called_once_with(self.cluster)
        for node in serialized_nodes:
            self.assertEqual(node['tasks'], [])

    def test_serialize_primary_and_non(self, task_metadata_mock):
        self.setup_env([
            {'roles': ['controller'], 'pending_addition': True},
            {'roles': ['controller'], 'pending_addition': True}])
        task_metadata_mock.return_value = TASKS
        serialized_nodes = deployment_serializers.serialize(
            self.cluster, self.nodes)
        task_metadata_mock.assert_called_once_with(self.cluster)
        for node in serialized_nodes:
            self.assertEqual(len(node['tasks']), 2)
