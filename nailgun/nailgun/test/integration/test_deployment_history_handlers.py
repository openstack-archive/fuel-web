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
import csv
import mock
import six

from nailgun import consts
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import mock_rpc
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
                'version': 'newton-10.0'
            }
        }

    @mock_rpc()
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_history_collection_handler(self, tasks_mock):
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
                }
                for node in cluster.nodes
                for task_no in six.moves.range(1, 1 + self.tasks_amt)
            ],
            response.json_body
        )

    @mock_rpc()
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_history_task_handler(self, tasks_mock):

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
            } for node in cluster.nodes],
            response.json_body
        )

    @mock_rpc()
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_unexisting_task_filter_returning_nothing(self, tasks_mock):
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
            headers=self.default_headers
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [],
            response.json_body
        )

    @mock_rpc()
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_history_task_handler_work_without_snapshot(self, tasks_mock):
        """Test that history task handler working without snapshot.

        Checks that if not valid graph snapshot is provided output will
        return to old history format without unwrapped tasks parameters.
        """
        tasks_mock.return_value = self.test_tasks

        cluster = self.env.create(**self.cluster_parameters)

        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)
        deployment_task = next(
            t for t in supertask.subtasks
            if t.name == consts.TASK_NAMES.deployment
        )
        deployment_task.tasks_snapshot = None
        self.db.flush()
        response = self.app.get(
            reverse(
                'DeploymentHistoryCollectionHandler',
                kwargs={
                    'transaction_id': deployment_task.id
                }
            ) + '?tasks_names=test1,nosuchtask',
            headers=self.default_headers
        )
        self.assertEqual(200, response.status_code)
        self.assertItemsEqual(
            [{
                'task_name': 'test1',
                'node_id': node.uid,
                'status': 'pending',
                'time_start': None,
                'time_end': None,
            } for node in cluster.nodes],
            response.json_body
        )

    @mock_rpc()
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_history_task_with_bad_status_param(self, tasks_mock):
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
            ) + '?statuses=NOTEXISTINGTYPE',
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual("Statuses parameter could be only: pending, ready, "
                         "running, error, skipped",
                         response.json_body['message'])

    @mock_rpc()
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_history_task_with_empty_statuses(self, tasks_mock):
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
            ) + '?statuses=',
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(200, response.status_code)

    @mock_rpc()
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_history_collection_handler_csv(self, tasks_mock):
        self.maxDiff = None
        tasks_mock.return_value = self.test_tasks

        cluster = self.env.create(**self.cluster_parameters)

        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)
        deployment_task = next(
            t for t in supertask.subtasks
            if t.name == consts.TASK_NAMES.deployment
        )

        headers = self.default_headers.copy()
        headers['accept'] = 'text/csv'

        response = self.app.get(
            reverse(
                'DeploymentHistoryCollectionHandler',
                kwargs={
                    'transaction_id': deployment_task.id
                }
            ),
            headers=headers
        )

        reader = csv.reader(response.body.strip().split('\n'))
        rows = list(reader)

        self.assertItemsEqual(
            rows,
            [['task_name',
              'node_id',
              'status',
              'type',
              'time_start',
              'time_end'],
             ['test2', cluster.nodes[0].uid, 'pending', 'puppet', '', ''],
             ['test1', cluster.nodes[0].uid, 'pending', 'puppet', '', '']])
