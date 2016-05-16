# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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
import six

from nailgun import consts
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestDeploymentHistoryHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestDeploymentHistoryHandlers, self).setUp()
        self.tasks_amt = 2
        self.test_tasks = [
            {
                'id': 'test{}'.format(task_no),
                'task_name': 'test{}'.format(task_no),
                'parameters': {'param1': 'value1'},
                'type': 'puppet',
                'roles': '*',
                'version': '2.1.0',
                'requires': ['pre_deployment_end']
            } for task_no in six.moves.range(1, 1 + self.tasks_amt)
        ]
        self.cluster_parameters = {
            'nodes_kwargs': [
                {
                    'roles': ['controller'],
                    'pending_addition': True
                },
            ],
            'release_kwargs': {
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0'
            }
        }

    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_history_collection_handler(self, tasks_mock, _):
        tasks_mock.return_value = self.test_tasks

        cluster = self.env.create(**self.cluster_parameters)

        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)
        deployment_task = next(
            t for t in supertask.subtasks
            if t.name == consts.TASK_NAMES.deployment
        )

        response = self.app.get(
            reverse(
                'DeploymentHistoryCollectionHandler',
                kwargs={
                    'transaction_id': deployment_task.id
                }
            ),
            headers=self.default_headers
        )

        self.assertItemsEqual(
            [
                {
                    'id': 'test{}'.format(task_no),
                    'task_name': 'test{}'.format(task_no),
                    'parameters': {'param1': 'value1'},
                    'roles': '*',
                    'type': 'puppet',
                    'version': '2.1.0',
                    'requires': ['pre_deployment_end'],
                    'node_id': node.uid,
                    'status': 'pending',
                    'time_start': None,
                    'time_end': None,
                    'custom': {}
                }
                for node in cluster.nodes
                for task_no in six.moves.range(1, 1 + self.tasks_amt)
            ],
            response.json_body
        )

    @mock.patch('nailgun.task.task.rpc.cast')
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_history_task_handler(self, tasks_mock, _):

        tasks_mock.return_value = self.test_tasks

        cluster = self.env.create(**self.cluster_parameters)

        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)
        deployment_task = next(
            t for t in supertask.subtasks
            if t.name == consts.TASK_NAMES.deployment
        )

        response = self.app.get(
            reverse(
                'DeploymentHistoryCollectionHandler',
                kwargs={
                    'transaction_id': deployment_task.id
                }
            ) + '?tasks_names=test1',
            headers=self.default_headers
        )

        self.assertItemsEqual(
            [{
                'id': 'test1',
                'task_name': 'test1',
                'parameters': {'param1': 'value1'},
                'roles': '*',
                'type': 'puppet',
                'version': '2.1.0',
                'requires': ['pre_deployment_end'],
                'node_id': node.uid,
                'status': 'pending',
                'time_start': None,
                'time_end': None,
                'custom': {}
            } for node in cluster.nodes],
            response.json_body
        )

    @mock.patch('nailgun.task.task.rpc.cast')
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_history_task_not_found_returns_empty(self, tasks_mock, _):
        tasks_mock.return_value = self.test_tasks

        cluster = self.env.create(**self.cluster_parameters)

        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)
        deployment_task = next(
            t for t in supertask.subtasks
            if t.name == consts.TASK_NAMES.deployment
        )

        response = self.app.get(
            reverse(
                'DeploymentHistoryCollectionHandler',
                kwargs={
                    'transaction_id': deployment_task.id
                }
            ) + '?tasks_names=NOSUCHTASK',
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json_body)

    @mock.patch('nailgun.task.task.rpc.cast')
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_history_task_handler_work_without_snapshot(self, tasks_mock, _):
        # check that if not valid graph snapshot is provided output will return
        # to old history format without unwrapped tasks parameters
        tasks_mock.return_value = self.test_tasks

        cluster = self.env.create(**self.cluster_parameters)

        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)
        deployment_task = next(
            t for t in supertask.subtasks
            if t.name == consts.TASK_NAMES.deployment
        )
        deployment_task.tasks_snapshot = None
        self.db.commit()
        response = self.app.get(
            reverse(
                'DeploymentHistoryCollectionHandler',
                kwargs={
                    'transaction_id': deployment_task.id
                }
            ) + '?tasks_names=test1,nosuchtask',
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(200, response.status_code)
        self.assertItemsEqual(
            [{
                'deployment_graph_task_name': 'test1',
                'node_id': node.uid,
                'status': 'pending',
                'time_start': None,
                'time_end': None,
                'custom': {}
            } for node in cluster.nodes],
            response.json_body
        )
