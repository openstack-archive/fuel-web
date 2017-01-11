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

from nailgun import consts
from nailgun import objects
from nailgun.rpc import receiver
from nailgun.transactions import manager

from nailgun.test import base


class TestTransactionManager(base.BaseIntegrationTest):

    def setUp(self):
        super(TestTransactionManager, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"status": consts.NODE_STATUSES.provisioned},
                {"status": consts.NODE_STATUSES.provisioned, "online": False},
            ],
            release_kwargs={
                'version': 'mitaka-9.0',
                'operating_system': consts.RELEASE_OS.ubuntu
            })
        self.graph = objects.DeploymentGraph.create_for_model(
            {
                'tasks': [
                    {
                        'id': 'test_task',
                        'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                        'roles': ['/.*/']
                    },
                ],
                'name': 'test_graph',
            },
            instance=self.cluster,
            graph_type='test_graph')
        self.manager = manager.TransactionsManager(self.cluster.id)
        self.receiver = receiver.NailgunReceiver
        self.expected_metadata = {
            'fault_tolerance_groups': [],
            'node_statuses_transitions': {
                'successful': {'status': consts.NODE_STATUSES.ready},
                'failed': {'status': consts.NODE_STATUSES.error},
                'stopped': {'status': consts.NODE_STATUSES.stopped}}
        }

    def _success(self, transaction_uuid):
        self.receiver.transaction_resp(
            task_uuid=transaction_uuid,
            nodes=[
                {'uid': n.uid, 'status': consts.NODE_STATUSES.ready}
                for n in self.cluster.nodes
            ],
            progress=100,
            status=consts.TASK_STATUSES.ready)

    def _fail(self, transaction_uuid):
        self.receiver.transaction_resp(
            task_uuid=transaction_uuid,
            nodes=[
                {'uid': n.uid, 'status': consts.NODE_STATUSES.error}
                for n in self.cluster.nodes
            ],
            progress=100,
            status=consts.TASK_STATUSES.error)

    def _check_timing(self, task):
        self.assertIsNotNone(task.time_start)
        self.assertIsNotNone(task.time_end)
        self.assertLessEqual(task.time_start, task.time_end)

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_graph(self, rpc_mock):
        task = self.manager.execute(graphs=[{"type": "test_graph"}])

        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[0].uuid,
                    'tasks_graph': {
                        None: [],
                        self.cluster.nodes[0].uid: [
                            {
                                'id': 'test_task',
                                'type': 'puppet',
                                'fail_on_error': True,
                                'parameters': {'cwd': '/'}
                            },
                        ]
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': False,
                    'debug': False,
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }])

        self._success(task.subtasks[0].uuid)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
        self._check_timing(task)
        self.assertEqual(
            consts.CLUSTER_STATUSES.operational, self.cluster.status
        )

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_few_graphs(self, rpc_mock):
        objects.DeploymentGraph.create_for_model(
            {
                'tasks': [
                    {
                        'id': 'super-mega-other-task',
                        'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                        'roles': ['/.*/']
                    },
                ],
                'name': 'test_graph_2',
            },
            instance=self.cluster,
            graph_type='test_graph_2')

        task = self.manager.execute(graphs=[
            {"type": "test_graph"},
            {"type": "test_graph_2"},
        ])

        self.assertItemsEqual(
            ["test_graph", "test_graph_2"],
            [sub.graph_type for sub in task.subtasks])

        # Only a message for the first graph should be sent, because
        # the second graph should be sent by RPC receiver once first
        # one is completed.
        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[0].uuid,
                    'tasks_graph': {
                        None: [],
                        self.cluster.nodes[0].uid: [
                            {
                                'id': 'test_task',
                                'type': 'puppet',
                                'fail_on_error': True,
                                'parameters': {'cwd': '/'}
                            },
                        ]
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': False,
                    'debug': False
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }])

        # Consider we've got success from Astute.
        self._success(task.subtasks[0].uuid)

        # It's time to send the second graph to execution.
        rpc_mock.cast.assert_called_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[1].uuid,
                    'tasks_graph': {
                        None: [],
                        self.cluster.nodes[0].uid: [
                            {
                                'id': 'super-mega-other-task',
                                'type': 'puppet',
                                'fail_on_error': True,
                                'parameters': {'cwd': '/'}
                            },
                        ]
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': False,
                    'debug': False
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }])

        # Consider we've got success from Astute.
        self._success(task.subtasks[1].uuid)
        self._check_timing(task.subtasks[1])
        # Ensure the top leve transaction is ready.
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_few_graphs_first_fail(self, rpc_mock):
        objects.DeploymentGraph.create_for_model(
            {
                'tasks': [
                    {
                        'id': 'super-mega-other-task',
                        'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                        'roles': ['/.*/']
                    },
                ],
                'name': 'test_graph_2',
            },
            instance=self.cluster,
            graph_type='test_graph_2')

        task = self.manager.execute(graphs=[
            {"type": "test_graph"},
            {"type": "test_graph_2"},
        ])

        self.assertItemsEqual(
            ["test_graph", "test_graph_2"],
            [sub.graph_type for sub in task.subtasks])

        # Only a message for the first graph should be sent, because
        # the second graph should be sent by RPC receiver once first
        # one is completed.
        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[0].uuid,
                    'tasks_graph': {
                        None: [],
                        self.cluster.nodes[0].uid: [
                            {
                                'id': 'test_task',
                                'type': 'puppet',
                                'fail_on_error': True,
                                'parameters': {'cwd': '/'}
                            },
                        ]
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': False,
                    'debug': False

                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }])

        self._fail(task.subtasks[0].uuid)

        self.assertEqual(rpc_mock.cast.call_count, 1)
        self.assertEqual(task.status, consts.TASK_STATUSES.error)
        self._check_timing(task.subtasks[0])
        self._check_timing(task.subtasks[1])
        self.assertEqual(
            consts.CLUSTER_STATUSES.partially_deployed, self.cluster.status
        )

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_w_task(self, rpc_mock):
        self.graph.tasks.append(objects.DeploymentGraphTask.create(
            {
                'id': 'test_task_2',
                'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                'roles': ['/.*/']
            }))

        task = self.manager.execute(graphs=[
            {
                "type": "test_graph",
                "tasks": ["test_task"],
            }])

        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[0].uuid,
                    'tasks_graph': {
                        None: [],
                        self.cluster.nodes[0].uid: mock.ANY,
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': False,
                    'debug': False

                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }])

        tasks_graph = rpc_mock.cast.call_args[0][1][0]['args']['tasks_graph']
        self.assertItemsEqual(tasks_graph[self.cluster.nodes[0].uid], [
            {
                'id': 'test_task',
                'type': 'puppet',
                'fail_on_error': True,
                'parameters': {'cwd': '/'}
            },
            {
                'id': 'test_task_2',
                'type': 'skipped',
                'fail_on_error': False,
            }
        ])

        self._success(task.subtasks[0].uuid)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_w_non_existing_task(self, rpc_mock):
        task = self.manager.execute(graphs=[
            {
                "type": "test_graph",
                "tasks": ["non_exist"],
            }])

        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[0].uuid,
                    'tasks_graph': {
                        None: [],
                        self.cluster.nodes[0].uid: [
                            {
                                'id': 'test_task',
                                'type': 'skipped',
                                'fail_on_error': False,
                            },
                        ]
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': False,
                    'debug': False
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }])

        self._success(task.subtasks[0].uuid)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_dry_run(self, rpc_mock):
        node = self.cluster.nodes[0]
        node.pending_roles = ['compute']
        self.cluster.status = consts.CLUSTER_STATUSES.new

        task = self.manager.execute(
            graphs=[{"type": "test_graph"}], dry_run=True)

        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[0].uuid,
                    'tasks_graph': {
                        None: [],
                        self.cluster.nodes[0].uid: [
                            {
                                'id': 'test_task',
                                'type': 'puppet',
                                'fail_on_error': True,
                                'parameters': {'cwd': '/'}
                            },
                        ]
                    },
                    'tasks_directory': {},
                    'dry_run': True,
                    'noop_run': False,
                    'debug': False
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }])

        self._success(task.subtasks[0].uuid)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
        self.assertEqual(['compute'], node.pending_roles)
        self.assertEqual(consts.CLUSTER_STATUSES.new, self.cluster.status)

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_noop_run(self, rpc_mock):
        node = self.cluster.nodes[0]
        node.pending_roles = ['compute']
        self.cluster.status = consts.CLUSTER_STATUSES.new

        task = self.manager.execute(
            graphs=[{"type": "test_graph"}], noop_run=True)

        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[0].uuid,
                    'tasks_graph': {
                        None: [],
                        self.cluster.nodes[0].uid: [
                            {
                                'id': 'test_task',
                                'type': 'puppet',
                                'fail_on_error': True,
                                'parameters': {'cwd': '/'}
                            },
                        ]
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': True,
                    'debug': False
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }])

        self._success(task.subtasks[0].uuid)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
        self.assertEqual(['compute'], node.pending_roles)
        self.assertEqual(consts.CLUSTER_STATUSES.new, self.cluster.status)

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_graph_fails_on_some_nodes(self, rpc_mock):
        task = self.manager.execute(graphs=[{"type": "test_graph"}])
        self.assertNotEqual(consts.TASK_STATUSES.error, task.status)
        self.assertEqual(1, rpc_mock.cast.call_count)

        self.receiver.transaction_resp(
            task_uuid=task.uuid,
            nodes=[
                {'uid': n.uid, 'status': consts.NODE_STATUSES.error}
                for n in self.cluster.nodes[:1]
            ] + [
                {'uid': n.uid, 'status': consts.NODE_STATUSES.ready}
                for n in self.cluster.nodes[1:]
            ],
            progress=100,
            status=consts.TASK_STATUSES.ready)
        self._success(task.subtasks[0].uuid)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
        self.assertEqual(
            consts.CLUSTER_STATUSES.partially_deployed, self.cluster.status
        )

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_on_one_node(self, rpc_mock):
        node = self.env.create_node(
            cluster_id=self.cluster.id, pending_roles=["compute"],
            status=consts.NODE_STATUSES.ready
        )

        task = self.manager.execute(graphs=[
            {
                "type": "test_graph",
                "nodes": [node.id],
            }])

        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[0].uuid,
                    'tasks_graph': {
                        None: [],
                        node.uid: [
                            {
                                'id': 'test_task',
                                'type': 'puppet',
                                'fail_on_error': True,
                                'parameters': {'cwd': '/'}
                            },
                        ]
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': False,
                    'debug': False
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }]
        )

        self._success(task.subtasks[0].uuid)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_with_node_filter(self, rpc_mock):
        node = self.env.create_node(
            cluster_id=self.cluster.id, pending_deletion=True,
            roles=["compute"]
        )
        objects.DeploymentGraph.create_for_model(
            {
                'tasks': [
                    {
                        'id': 'delete_node',
                        'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                        'roles': ['/.*/']
                    },
                ],
                'name': 'deletion_graph',
                'node_filter': '$.pending_deletion'
            },
            instance=self.cluster,
            graph_type='deletion_graph',
        )

        task = self.manager.execute(graphs=[{"type": "deletion_graph"}])
        self.assertNotEqual(consts.TASK_STATUSES.error, task.status)
        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[0].uuid,
                    'tasks_graph': {
                        None: [],
                        node.uid: [
                            {
                                'id': 'delete_node',
                                'type': 'puppet',
                                'fail_on_error': True,
                                'parameters': {'cwd': '/'}
                            },
                        ]
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': False,
                    'debug': False
                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }]
        )

        self._success(task.subtasks[0].uuid)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

    @mock.patch('nailgun.transactions.manager.rpc')
    def test_execute_for_primary_tags(self, rpc_mock):
        self.graph.tasks.append(objects.DeploymentGraphTask.create(
            {
                'id': 'test_task_2',
                'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                'roles': ['primary-controller']
            }))

        node = self.env.create_node(
            cluster_id=self.cluster.id, roles=["controller"],
            status=consts.NODE_STATUSES.stopped
        )

        task = self.manager.execute(graphs=[
            {
                "type": "test_graph",
                "tasks": ["test_task_2"],
                "nodes": [node.id]
            }])

        rpc_mock.cast.assert_called_once_with(
            'naily',
            [{
                'args': {
                    'tasks_metadata': self.expected_metadata,
                    'task_uuid': task.subtasks[0].uuid,
                    'tasks_graph': {
                        None: [],
                        node.uid: mock.ANY,
                    },
                    'tasks_directory': {},
                    'dry_run': False,
                    'noop_run': False,
                    'debug': False

                },
                'respond_to': 'transaction_resp',
                'method': 'task_deploy',
                'api_version': '1'
            }])

        tasks_graph = rpc_mock.cast.call_args[0][1][0]['args']['tasks_graph']
        self.assertItemsEqual(tasks_graph[node.uid], [
            {
                'id': 'test_task_2',
                'type': 'puppet',
                'fail_on_error': True,
                'parameters': {'cwd': '/'}
            },
            {
                'id': 'test_task',
                'type': 'skipped',
                'fail_on_error': False,
            }
        ])

        self._success(task.subtasks[0].uuid)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)
