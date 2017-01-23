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

from nailgun import consts
from nailgun.transactions import manager

from nailgun.test.base import BaseUnitTest


class TestMakeAstuteMessage(BaseUnitTest):

    maxDiff = None

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.lcm')
    def test_make_astute_message(self, lcm_mock, obj_mock):
        resolver = mock.MagicMock()
        context = mock.MagicMock()
        tx = mock.MagicMock(
            dry_run=False,
            cache={'dry_run': False, 'noop_run': False, 'debug': False}
        )
        graph = {
            'tasks': mock.MagicMock(),
            'on_success': {'node_attributes': {}},
            'on_error': {},
        }
        tasks_directory = mock.MagicMock()
        tasks_graph = mock.MagicMock()
        tasks_metadata = {
            'node_statuses_transitions': {
                'successful': {},
                'failed': {'status': consts.NODE_STATUSES.error},
                'stopped': {'status': consts.NODE_STATUSES.stopped},
            }
        }
        lcm_mock.TransactionSerializer.serialize.return_value = (
            tasks_directory, tasks_graph, {}
        )
        result = manager.make_astute_message(tx, context, graph, resolver)
        self.assertEqual(
            {
                'api_version': manager.settings.VERSION['api'],
                'method': 'task_deploy',
                'respond_to': 'transaction_resp',
                'args': {
                    'task_uuid': tx.uuid,
                    'tasks_directory': tasks_directory,
                    'tasks_graph': tasks_graph,
                    'tasks_metadata': tasks_metadata,
                    'dry_run': False,
                    'noop_run': False,
                    'debug': False
                }
            },
            result
        )
        lcm_mock.TransactionSerializer.serialize.assert_called_once_with(
            context, graph['tasks'], resolver
        )
        obj_mock.DeploymentHistoryCollection.create.assert_called_once_with(
            tx, tasks_graph
        )


class TestRemoveObsoleteTasks(BaseUnitTest):

    @mock.patch('nailgun.transactions.manager.db')
    @mock.patch('nailgun.transactions.manager.objects')
    def test_remove_obsolete_tasks(self, objects_mock, db_mock):
        tasks = [
            mock.MagicMock(status=consts.TASK_STATUSES.ready),
            mock.MagicMock(status=consts.TASK_STATUSES.error),
            mock.MagicMock(status=consts.TASK_STATUSES.running),
        ]
        objects_mock.TaskCollection.order_by.return_value = tasks

        cluster = mock.MagicMock()
        manager._remove_obsolete_tasks(cluster)

        db_mock().flush.assert_called_once_with()
        objects_mock.TaskCollection.filter_by.assert_called_once_with(
            mock.ANY, cluster_id=cluster.id
        )
        objects_mock.TaskCollection.order_by(
            objects_mock.TaskCollection.get_cluster_tasks.return_value, 'id'
        )
        objects_mock.Task.delete.assert_has_calls([
            mock.call(tasks[0]), mock.call(tasks[1])
        ])


class TestNodeForRedeploy(BaseUnitTest):

    def test_is_node_for_redeploy(self):
        self.assertFalse(manager._is_node_for_redeploy(None))

        self.assertTrue(manager._is_node_for_redeploy(mock.MagicMock(
            pending_addition=True, status=consts.NODE_STATUSES.discover,
            progress=0, error_type=None
        )))
        self.assertFalse(manager._is_node_for_redeploy(mock.MagicMock(
            pending_addition=False, status=consts.NODE_STATUSES.ready,
            progress=0, error_type=None
        )))
        self.assertTrue(manager._is_node_for_redeploy(mock.MagicMock(
            pending_addition=True, status=consts.NODE_STATUSES.ready,
            progress=0, error_type=None
        )))
        self.assertTrue(
            manager._is_node_for_redeploy(mock.MagicMock(
                pending_addition=False, error_type=consts.NODE_ERRORS.deploy,
                progress=0, status=consts.NODE_STATUSES.error
            ))
        )
        self.assertTrue(
            manager._is_node_for_redeploy(mock.MagicMock(
                pending_addition=False, status=consts.NODE_STATUSES.stopped,
                progress=0, error_type=None
            ))
        )


class TestAdjustTasksToRun(BaseUnitTest):
    @mock.patch('nailgun.transactions.manager.objects')
    def test_adjust_tasks_if_no_legacy(self, objects_mock):
        cluster_obj = objects_mock.Cluster
        tasks = [
            {'id': 'task1', 'type': consts.ORCHESTRATOR_TASK_TYPES.puppet},
            {'id': 'task2', 'type': consts.ORCHESTRATOR_TASK_TYPES.group},
            {'id': 'task3', 'type': consts.ORCHESTRATOR_TASK_TYPES.shell},
            {'id': 'task4', 'type': consts.ORCHESTRATOR_TASK_TYPES.skipped}
        ]
        graph = {'tasks': tasks[:]}
        cluster_obj.is_propagate_task_deploy_enabled.return_value = False

        cluster = mock.MagicMock()
        manager._adjust_graph_tasks(graph, cluster, None, None)
        self.assertEqual(tasks, graph['tasks'])
        cluster_obj.is_propagate_task_deploy_enabled.assert_called_once_with(
            cluster
        )
        # filter result
        manager._adjust_graph_tasks(graph, cluster, None, ['task1'])
        tasks[2]['type'] = consts.ORCHESTRATOR_TASK_TYPES.skipped
        self.assertEqual(tasks, graph['tasks'])

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.legacy_tasks_adapter')
    def test_adjust_tasks_with_legacy(self, adapter_mock, objects_mock):
        cluster_obj = objects_mock.Cluster
        tasks = [
            {'id': 'tasks2', 'type': consts.ORCHESTRATOR_TASK_TYPES.group},
        ]
        graph = {'tasks': tasks[:], 'type': 'provision'}
        cluster_obj.is_propagate_task_deploy_enabled.return_value = True
        adapter_mock.adapt_legacy_tasks.return_value = tasks

        cluster = mock.MagicMock()
        resolver = mock.MagicMock()
        manager._adjust_graph_tasks(graph, cluster, resolver, None)
        self.assertEqual(tasks, graph['tasks'])

        cluster_obj.is_propagate_task_deploy_enabled.assert_called_once_with(
            cluster
        )
        adapter_mock.adapt_legacy_tasks.assert_called_once_with(
            graph['tasks'], None, resolver
        )
        graph2 = {
            'tasks': tasks[:], 'type': consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE
        }
        manager._adjust_graph_tasks(graph2, cluster, resolver, None)
        self.assertEqual(tasks, graph2['tasks'])

        cluster_obj.get_legacy_plugin_tasks.assert_called_once_with(cluster)
        adapter_mock.adapt_legacy_tasks.assert_called_with(
            tasks, cluster_obj.get_legacy_plugin_tasks.return_value, resolver
        )


class TestUpdateNodes(BaseUnitTest):
    @mock.patch('nailgun.transactions.manager.objects')
    def test_delete_node_from_cluster(self, obj_mock):
        transaction = mock.MagicMock(dry_run=False, noop_run=False)
        nodes = [mock.MagicMock(uid='1')]
        node_params = {'1': {'status': 'deleted'}}
        manager._update_nodes(transaction, nodes, node_params)
        obj_mock.Node.remove_from_cluster.assert_called_once_with(nodes[0])

    @mock.patch('nailgun.transactions.manager.objects')
    def test_delete_node_from_cluster_if_dry_run(self, obj_mock):
        transaction = mock.MagicMock(dry_run=True, noop_run=False)
        nodes = [mock.MagicMock(uid='1')]
        node_params = {'1': {'status': 'deleted'}}
        manager._update_nodes(transaction, nodes, node_params)
        self.assertEqual(0, obj_mock.Node.remove_from_cluster.call_count)

    @mock.patch('nailgun.transactions.manager.notifier')
    def test_set_error_status(self, notifier_mock):
        transaction = mock.MagicMock(dry_run=False, noop_run=False)
        nodes = [mock.MagicMock(uid='1', error_type=None)]
        node_params = {
            '1': {
                'status': 'error', 'error_type': consts.NODE_ERRORS.provision
            }
        }
        manager._update_nodes(transaction, nodes, node_params)
        self.assertEqual(consts.NODE_ERRORS.provision, nodes[0].error_type)
        notifier_mock.notify.assert_called_once_with(
            consts.NOTIFICATION_TOPICS.error,
            "Node '{0}' failed: Unknown error".format(nodes[0].name),
            cluster_id=transaction.cluster_id,
            node_id=nodes[0].uid,
            task_uuid=transaction.uuid
        )

    @mock.patch('nailgun.transactions.manager.notifier')
    def test_set_default_error_type(self, notifier_mock):
        transaction = mock.MagicMock(dry_run=False, noop_run=False)
        nodes = [mock.MagicMock(uid='1', error_type=None)]
        node_params = {'1': {'status': 'error', 'error_msg': 'error'}}
        manager._update_nodes(transaction, nodes, node_params)
        self.assertEqual(consts.NODE_ERRORS.deploy, nodes[0].error_type)
        notifier_mock.notify.assert_called_once_with(
            consts.NOTIFICATION_TOPICS.error,
            "Node '{0}' failed: error".format(nodes[0].name),
            cluster_id=transaction.cluster_id,
            node_id=nodes[0].uid,
            task_uuid=transaction.uuid
        )

    @mock.patch('nailgun.transactions.manager.notifier')
    def test_handle_error_status_for_node_if_dry_run(self, notifier_mock):
        transaction = mock.MagicMock(dry_run=True, noop_run=False)
        nodes = [mock.MagicMock(uid='1', error_type=None)]
        node_params = {'1': {'status': 'error'}}
        manager._update_nodes(transaction, nodes, node_params)
        self.assertIsNone(nodes[0].error_type)
        self.assertEqual(0, notifier_mock.notify.call_count)

    def test_update_node_progress(self):
        transaction = mock.MagicMock(dry_run=False, noop_run=False)
        nodes = [mock.MagicMock(uid='1', progress=0)]
        node_params = {'1': {'progress': 10}}
        manager._update_nodes(transaction, nodes, node_params)
        self.assertEqual(10, nodes[0].progress)

        transaction.dry_run = True
        transaction.noop_run = False
        node_params = {'1': {'progress': 20}}
        manager._update_nodes(transaction, nodes, node_params)
        self.assertEqual(20, nodes[0].progress)

    def test_update_node_status(self):
        transaction = mock.MagicMock(dry_run=False, noop_run=False)
        nodes = [mock.MagicMock(uid='1', status=consts.NODE_STATUSES.discover)]
        node_params = {'1': {'status': consts.NODE_STATUSES.ready}}
        manager._update_nodes(transaction, nodes, node_params)
        self.assertEqual(consts.NODE_STATUSES.ready, nodes[0].status)

    def test_update_node_status_if_dry_run(self):
        transaction = mock.MagicMock(dry_run=True, noop_run=False)
        nodes = [mock.MagicMock(uid='1', status=consts.NODE_STATUSES.discover)]
        node_params = {'1': {'status': consts.NODE_STATUSES.ready}}
        manager._update_nodes(transaction, nodes, node_params)
        self.assertEqual(consts.NODE_STATUSES.discover, nodes[0].status)


class TestGetNodesToRun(BaseUnitTest):
    @mock.patch('nailgun.transactions.manager.objects')
    def test_get_nodes_by_ids(self, objects_mock):
        nodes_obj_mock = objects_mock.NodeCollection
        cluster = mock.MagicMock()
        node_ids = [1, 2]
        filtered_nodes = manager._get_nodes_to_run(cluster, None, node_ids)
        nodes_obj_mock.filter_by.assert_called_once_with(
            None, cluster_id=cluster.id, online=True
        )
        nodes_obj_mock.filter_by_list.assert_called_once_with(
            mock.ANY, 'id', node_ids
        )
        nodes_obj_mock.order_by.assert_called_once_with(
            mock.ANY, 'id'
        )
        self.assertEqual(
            filtered_nodes, nodes_obj_mock.lock_for_update().all()
        )

    @mock.patch('nailgun.transactions.manager.objects')
    def test_get_by_node_filter(self, obj_mock):
        nodes_obj_mock = obj_mock.NodeCollection
        cluster = mock.MagicMock()
        node_filter = '$.pending_deletion'
        nodes_list = [
            {'id': 1, 'pending_deletion': False},
            {'id': 2, 'pending_deletion': True}
        ]
        nodes_obj_mock.to_list.return_value = nodes_list
        manager._get_nodes_to_run(cluster, node_filter)
        nodes_obj_mock.filter_by_list.assert_called_once_with(
            mock.ANY, 'id', [2]
        )

    @mock.patch('nailgun.transactions.manager.objects')
    def test_get_no_nodes_if_filter_returns_empty_list(self, obj_mock):
        nodes_obj_mock = obj_mock.NodeCollection
        cluster = mock.MagicMock()
        node_filter = '$.pending_deletion'
        nodes_list = [
            {'id': 1, 'pending_deletion': False},
            {'id': 2, 'pending_deletion': False}
        ]
        nodes_obj_mock.to_list.return_value = nodes_list
        manager._get_nodes_to_run(cluster, node_filter)
        nodes_obj_mock.filter_by_list.assert_called_once_with(
            mock.ANY, 'id', []
        )

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.yaql_ext')
    def test_ids_has_high_priority_then_node_filter(self, yaql_mock, obj_mock):
        nodes_obj_mock = obj_mock.NodeCollection
        cluster = mock.MagicMock()
        node_ids = [1, 2]
        node_filter = '$.pending_deletion'
        manager._get_nodes_to_run(cluster, node_filter, node_ids)
        nodes_obj_mock.filter_by_list.assert_called_once_with(
            mock.ANY, 'id', node_ids
        )
        self.assertEqual(0, yaql_mock.create_context.call_count)

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.yaql_ext')
    def test_get_all_nodes_with_empty_ids(self, yaql_mock, obj_mock):
        nodes_obj_mock = obj_mock.NodeCollection
        cluster = mock.MagicMock()
        node_ids = []
        node_filter = '$.pending_deletion'
        manager._get_nodes_to_run(cluster, node_filter, node_ids)
        self.assertEqual(0, yaql_mock.create_context.call_count)
        nodes_obj_mock.filter_by_list.assert_called_once_with(
            mock.ANY, 'id', []
        )

    @mock.patch('nailgun.transactions.manager.objects')
    def test_default_node_filter(self, obj_mock):
        nodes_obj_mock = obj_mock.NodeCollection
        cluster = mock.MagicMock()
        nodes_list = [
            {
                'id': 1, 'pending_deletion': False, 'pending_addition': False,
                'status': 'provisioned', 'error_type': None
            },
            {
                'id': 2, 'pending_deletion': False, 'pending_addition': False,
                'status': 'ready', 'error_type': None
            },
            {
                'id': 3, 'pending_deletion': False, 'pending_addition': False,
                'status': 'stopped', 'error_type': None
            },
            {
                'id': 4, 'pending_deletion': True, 'pending_addition': False,
                'status': 'stopped', 'error_type': None
            },
            {
                'id': 5, 'pending_deletion': False, 'pending_addition': True,
                'status': 'stopped', 'error_type': None
            },
        ]
        nodes_obj_mock.to_list.return_value = nodes_list
        manager._get_nodes_to_run(cluster, None)
        nodes_obj_mock.filter_by_list.assert_called_once_with(
            mock.ANY, 'id', [1, 2, 3]
        )


class TestGetCurrentState(BaseUnitTest):
    def setUp(self):
        super(TestGetCurrentState, self).setUp()
        self.cluster = mock.MagicMock()
        self.nodes = [
            mock.MagicMock(
                uid='1', pending_addition=False, status='ready',
                error_type=None
            ),
            mock.MagicMock(
                uid='2', pending_addition=False, status='ready',
                error_type=None
            )
        ]
        self.tasks = [
            {'id': 'task1', 'type': consts.ORCHESTRATOR_TASK_TYPES.puppet},
            {'id': 'task2', 'type': consts.ORCHESTRATOR_TASK_TYPES.shell},
            {'id': 'task3', 'type': consts.ORCHESTRATOR_TASK_TYPES.group}
        ]

    def test_get_current_state_with_force(self):
        current_state = manager._get_current_state(
            self.cluster, self.nodes, self.tasks, force=True
        )
        self.assertEqual({}, current_state)

    @mock.patch('nailgun.transactions.manager.objects')
    def test_get_current_state_if_there_is_no_deployment(self, objects_mock):
        txs_mock = objects_mock.TransactionCollection
        txs_mock.get_successful_transactions_per_task.return_value = []
        nodes = {'1': self.nodes[0], '2': self.nodes[1], 'master': None}
        current_state = manager._get_current_state(
            self.cluster, self.nodes, self.tasks
        )
        self.assertEqual({}, current_state)
        txs_mock.get_successful_transactions_per_task.assert_called_once_with(
            self.cluster.id, ['task1', 'task2'], nodes
        )

    @mock.patch('nailgun.transactions.manager.objects')
    def test_assemble_current_state(self, objects_mock):
        txs_mock = objects_mock.TransactionCollection
        transactions = [
            (1, '1', 'task1'), (2, '1', 'task2'), (2, '2', 'task2')
        ]
        txs_mock.get_successful_transactions_per_task.return_value = \
            transactions

        objects_mock.Transaction.get_deployment_info.side_effect = [
            {'common': {'key1': 'value1'},
             'nodes': {'1': {'key11': 'value11'}}},
            {'common': {'key2': 'value2'},
             'nodes': {'1': {'key21': 'value21'}, '2': {'key22': 'value22'}}},
        ]

        current_state = manager._get_current_state(
            self.cluster, self.nodes, self.tasks
        )
        expected_state = {
            'task1': {
                'common': {'key1': 'value1'},
                'nodes': {'1': {'key11': 'value11'}}
            },
            'task2': {
                'common': {'key2': 'value2'},
                'nodes': {
                    '1': {'key21': 'value21'},
                    '2': {'key22': 'value22'}
                },
            }
        }

        self.assertEqual(expected_state, current_state)


class TestPrepareNodes(BaseUnitTest):
    def test_apply_only_for_involved_nodes(self):
        nodes = [
            mock.MagicMock(
                uid=1, progress=0, error_type='deployment', error_msg='test'
            ),
            mock.MagicMock(
                uid=2, progress=0, error_type='provision', error_msg='test2'
            ),
        ]
        manager._prepare_nodes(nodes, False, {2})
        self.assertEqual(0, nodes[0].progress)
        self.assertEqual('deployment', nodes[0].error_type)
        self.assertEqual('test', nodes[0].error_msg)
        self.assertEqual(1, nodes[1].progress)
        self.assertIsNone(nodes[1].error_type)
        self.assertIsNone(nodes[1].error_msg)

    def test_not_reset_error_if_dry_run(self):
        nodes = [
            mock.MagicMock(
                uid=1, progress=0, error_type='deployment', error_msg='test'
            )
        ]
        manager._prepare_nodes(nodes, True, {1})
        self.assertEqual(1, nodes[0].progress)
        self.assertEqual('deployment', nodes[0].error_type)
        self.assertEqual('test', nodes[0].error_msg)
