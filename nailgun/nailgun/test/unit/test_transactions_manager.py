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


@mock.patch('nailgun.transactions.manager.db')
@mock.patch('nailgun.transactions.manager.helpers', new=mock.MagicMock())
class TestTransactionsManager(BaseUnitTest):
    def setUp(self):
        self.manager = manager.TransactionsManager(1)

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.mule')
    def test_execute_if_success(self, mule_mock, objects_mock, db_mock):
        nodes = [
            mock.MagicMock(id=1, uid='1'), mock.MagicMock(id=2, uid='2')
        ]
        graph_types = 'graph1,graph2'
        objects_mock.TaskCollection.count.return_value = 0

        result = self.manager.execute(nodes, graph_types, False, debug=True)
        objects_mock.Transaction.create.assert_called_once_with({
            'name': self.manager.task_name,
            'cluster_id': self.manager.cluster_id,
            'status': consts.TASK_STATUSES.pending,
            'dry_run': False
        })

        db_mock().commit.assert_called_once_with()

        mule_mock.call_task_manager_async.assert_called_once_with(
            self.manager.__class__,
            '_execute_async_safe',
            self.manager.cluster_id,
            transaction_id=result.id,
            node_ids=[1, 2],
            graph_types=['graph1', 'graph2'],
            dry_run=False,
            debug=True
        )

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.mule')
    def test_execute_if_error(self, mule_mock, objects_mock, db_mock):
        objects_mock.TaskCollection.count.return_value = 0
        mule_mock.call_task_manager_async.side_effect = RuntimeError('test')

        result = self.manager.execute(None, None, True, task_names=['task1'])

        objects_mock.Transaction.create.assert_called_once_with({
            'name': self.manager.task_name,
            'cluster_id': self.manager.cluster_id,
            'status': consts.TASK_STATUSES.pending,
            'dry_run': True
        })

        db_mock().commit.assert_called_once_with()

        mule_mock.call_task_manager_async.assert_called_once_with(
            self.manager.__class__,
            '_execute_async_safe',
            self.manager.cluster_id,
            transaction_id=result.id,
            node_ids=None,
            graph_types=[consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE],
            dry_run=True,
            task_names=['task1']
        )

        objects_mock.Task.update.assert_called_once_with(
            result,
            {
                'status': consts.TASK_STATUSES.error,
                'progress': 100,
                'message': 'test'
            }
        )

    @mock.patch('nailgun.transactions.manager.objects')
    def test_execute_async_safe_if_success(self, objects_mock, db_mock):
        manager_mock = mock.MagicMock(spec=self.manager)
        manager.TransactionsManager._execute_async_safe(
            manager_mock, 1, graph=['test']
        )
        objects_mock.Transaction.get_by_uid.assert_called_once_with(
            1, fail_if_not_found=True
        )
        db_mock().commit.assert_called_once_with()
        manager_mock._execute_async.assert_called_once_with(
            objects_mock.Transaction.get_by_uid(), graph=['test']
        )

    @mock.patch('nailgun.transactions.manager.objects')
    def test_execute_async_safe_if_error(self, objects_mock, _):
        manager_mock = mock.MagicMock(spec=self.manager)
        manager_mock._execute_async.side_effect = ValueError("error")
        transaction = mock.MagicMock()
        objects_mock.Transaction.get_by_uid.return_value = transaction

        manager.TransactionsManager._execute_async_safe(
            manager_mock, 1, graph=['test']
        )
        objects_mock.Task.update.assert_called_once_with(
            transaction,
            {
                'status': consts.TASK_STATUSES.error,
                'progress': 100,
                'message': 'error'
            }
        )

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.rpc')
    @mock.patch('nailgun.transactions.manager.lcm')
    def test_execute_async_with_force(self, lcm_m, rpc_mo, obj_m, db_m):
        manager_mock = mock.MagicMock(spec=self.manager)
        cluster = mock.MagicMock()
        transaction = mock.MagicMock(cluster=cluster)
        nodes = [
            mock.MagicMock(id=1, uid='1', roles=[], pending_roles=['r1']),
            mock.MagicMock(id=2, uid='2', roles=['r2'], pending_roles=['r3'])
        ]
        message = {'args': {'test': 'value'}}

        node_ids = []
        graph_types = ['test']
        obj_m.Cluster.get_by_uid.return_value = cluster
        obj_m.NodeCollection.lock_for_update().all.return_value = nodes
        manager_mock._assemble_astute_message.side_effect = [message]

        manager.TransactionsManager._execute_async(
            manager_mock, transaction, node_ids, graph_types, force=True
        )

        obj_m.NodeCollection.filter_by.assert_called_once_with(
            None, cluster_id=cluster.id
        )
        obj_m.NodeCollection.order_by.assert_called_once_with(
            obj_m.NodeCollection.filter_by.return_value, 'id'
        )
        obj_m.NodeCollection.lock_for_update.assert_called_with(
            obj_m.NodeCollection.order_by.return_value
        )

        db_m().flush.assert_called_with()
        manager_mock._get_tasks.assert_called_with(
            cluster, mock.ANY, None, 'test'
        )
        manager_mock._get_expected_state.assert_called_once_with(
            cluster, nodes
        )
        self.assertEqual(
            0, manager_mock._get_current_state.call_count
        )
        manager_mock._dump_expected_state.assert_called_once_with(
            transaction, manager_mock._get_expected_state.return_value
        )
        lcm_m.TransactionContext.assert_called_once_with(
            manager_mock._get_expected_state.return_value, {}
        )

        transaction.create_subtask.assert_called_once_with(
            manager_mock.task_name,
            status=consts.TASK_STATUSES.pending,
            dry_run=False,
            graph_type=graph_types[0]
        )
        obj_m.Transaction.attach_tasks_snapshot.assert_called_with(
            transaction.create_subtask.return_value,
            manager_mock._get_tasks.return_value
        )
        manager_mock._assemble_astute_message.assert_called_with(
            transaction.create_subtask.return_value,
            lcm_m.TransactionContext.return_value,
            manager_mock._get_tasks.return_value,
            mock.ANY  # node_resolver
        )
        db_m().commit.assert_called_once_with()
        message['args']['dry_run'] = False
        rpc_mo.cast.assert_called_once_with(
            'naily', [message]
        )

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.rpc')
    @mock.patch('nailgun.transactions.manager.lcm')
    def test_execute_async_with_custom_nodes(self, lcm_m, rpc_mo, obj_m, db_m):
        manager_mock = mock.MagicMock(spec=self.manager)
        cluster = mock.MagicMock()
        transaction = mock.MagicMock(cluster=cluster)
        nodes = [
            mock.MagicMock(id=1, uid='1', roles=[], pending_roles=['r1']),
            mock.MagicMock(id=2, uid='2', roles=['r2'], pending_roles=['r3'])
        ]
        messages = [
            {'args': {'test': 'value1'}},
            {'args': {'test': 'value2'}}
        ]

        node_ids = [1, 2]
        graph_types = ['test1', 'test2']
        obj_m.Cluster.get_by_uid.return_value = cluster
        obj_m.NodeCollection.lock_for_update().all.return_value = nodes
        manager_mock._assemble_astute_message.side_effect = messages
        tasks = [[{'id': 't1'}], [{'id': 't2'}]]
        manager_mock._get_tasks.side_effect = tasks
        manager.TransactionsManager._execute_async(
            manager_mock, transaction, node_ids, graph_types, dry_run=True
        )

        obj_m.NodeCollection.filter_by_list.assert_called_once_with(
            obj_m.NodeCollection.filter_by.return_value,
            'id', node_ids
        )
        obj_m.NodeCollection.order_by.assert_called_once_with(
            obj_m.NodeCollection.filter_by_list.return_value, 'id'
        )
        obj_m.NodeCollection.lock_for_update.assert_called_with(
            obj_m.NodeCollection.order_by.return_value
        )

        db_m().flush.assert_called_with()
        manager_mock._get_current_state(
            cluster, nodes, manager.itertools.chain(*tasks)
        )
        lcm_m.TransactionContext.assert_called_once_with(
            manager_mock._get_expected_state.return_value,
            manager_mock._get_current_state.return_value
        )

        # the graphs are packed to dict, so order may be any
        transaction.create_subtask.assert_has_calls([
            mock.call(
                manager_mock.task_name,
                status=consts.TASK_STATUSES.pending,
                dry_run=True,
                graph_type=graph_type
            )
            for graph_type in graph_types
        ], any_order=True)

        obj_m.Transaction.attach_tasks_snapshot.assert_has_calls([
            mock.call(transaction.create_subtask.return_value, x)
            for x in tasks
        ])

        manager_mock._assemble_astute_message.assert_has_calls([
            mock.call(
                transaction.create_subtask.return_value,
                lcm_m.TransactionContext.return_value,
                x,
                mock.ANY  # node_resolver
            ) for x in tasks
        ])
        db_m().commit.assert_called_once_with()
        for m in messages:
            m['args']['dry_run'] = True

        rpc_mo.cast.assert_called_once_with(
            'naily', messages
        )

    @mock.patch('nailgun.transactions.manager.objects')
    def test_dump_expected_state(self, objects_mock, db_mock):
        cluster = mock.MagicMock()
        transaction = mock.MagicMock(cluster=cluster)
        state = mock.MagicMock()
        tx_obj = objects_mock.Transaction
        cluster_obj = objects_mock.Cluster

        self.manager._dump_expected_state(transaction, state)

        tx_obj.attach_deployment_info.assert_called_once_with(
            transaction, state
        )
        tx_obj.attach_cluster_settings.assert_called_once_with(
            transaction,
            {
                'editable': cluster_obj.get_editable_attributes.return_value
            }
        )

        tx_obj.attach_network_settings.assert_called_once_with(
            transaction, cluster_obj.get_network_attributes.return_value
        )
        db_mock().flush.assert_called_once_with()

    @mock.patch('nailgun.transactions.manager.deployment_serializers')
    def test_get_expected_state(self, serializer_mock, _):
        serializer_mock.serialize_for_lcm.return_value = [
            {'uid': '1'}
        ]
        cluster = mock.MagicMock()
        nodes = [mock.MagicMock(uid='1')]
        self.assertEqual(
            {None: {}, '1': {'uid': '1'}},
            self.manager._get_expected_state(cluster, nodes)
        )
        serializer_mock.serialize_for_lcm.assert_called_once_with(
            cluster, nodes
        )

    @mock.patch('nailgun.transactions.manager.objects')
    def test_get_current_state(self, objects_mock, _):
        cluster = mock.MagicMock()
        nodes = [
            mock.MagicMock(
                uid='1', pending_addition=False,
                status=consts.NODE_STATUSES.ready
            ),
            mock.MagicMock(
                uid='2', pending_addition=False,
                status=consts.NODE_STATUSES.discover
            ),
        ]
        tasks = [
            {'id': 't1', 'type': consts.ORCHESTRATOR_TASK_TYPES.skipped},
            {'id': 't2', 'type': consts.ORCHESTRATOR_TASK_TYPES.puppet},
            {'id': 't3', 'type': consts.ORCHESTRATOR_TASK_TYPES.group},
            {'id': 't4', 'type': consts.ORCHESTRATOR_TASK_TYPES.shell},
        ]

        transactions_mock = objects_mock.TransactionCollection
        tx1 = mock.MagicMock()
        tx2 = mock.MagicMock()

        transactions_mock.get_successful_transactions_per_task.return_value = [
            (tx1, '1', 't1'), (tx1, '2', 't2'), (tx1, 'master', 't3'),
            (tx2, '1', 't3'), (tx2, '1', 't4'), (tx2, 'master', 't1')
        ]
        objects_mock.Transaction.get_deployment_info.return_value = {
            '1': {'test': 'value'}
        }

        state = self.manager._get_current_state(cluster, nodes, tasks)

        transactions_mock.get_successful_transactions_per_task.\
            assert_called_once_with(
                cluster.id, ['t2', 't4'],
                dict(((n.uid, n) for n in nodes), master=None)
            )

        objects_mock.Transaction.get_deployment_info.assert_has_calls([
            mock.call(tx1.parent, node_uids=['1', 'master']),
            mock.call(tx2.parent, node_uids=['1', '1', 'master']),
        ])

        self.assertEqual(
            {
                't4': {'1': {'test': 'value'}},
                't2': {'2': {}},
                't3': {'1': {'test': 'value'}, 'master': {}},
                't1': {'1': {'test': 'value'}, 'master': {}}
            },
            state
        )

    @mock.patch('nailgun.transactions.manager.objects')
    def test_remove_obsolete_tasks(self, objects_mock, db_mock):
        tasks = [
            mock.MagicMock(status=consts.TASK_STATUSES.ready),
            mock.MagicMock(status=consts.TASK_STATUSES.error),
            mock.MagicMock(status=consts.TASK_STATUSES.running)
        ]
        objects_mock.TaskCollection.order_by.return_value = tasks
        cluster = mock.MagicMock()
        self.manager._remove_obsolete_tasks(cluster)
        db_mock().flush.assert_called_once_with()

        objects_mock.TaskCollection.get_cluster_tasks.assert_called_once_with(
            cluster_id=cluster.id
        )

        objects_mock.TaskCollection.order_by(
            objects_mock.TaskCollection.get_cluster_tasks.return_value, 'id'
        )
        objects_mock.Task.delete.assert_has_calls([
            mock.call(tasks[0]), mock.call(tasks[1])
        ])

    @mock.patch('nailgun.transactions.manager.objects')
    def test_acquire_cluster(self, objects_mock, _):
        cluster_mock = mock.MagicMock()
        objects_mock.Cluster.get_by_uid.return_value = cluster_mock
        objects_mock.TaskCollection.count.return_value = 0
        cluster = self.manager._acquire_cluster()
        self.assertIs(cluster_mock, cluster)
        objects_mock.Cluster.get_by_uid.assert_called_once_with(
            self.manager.cluster_id,
            fail_if_not_found=True,
            lock_for_update=True
        )
        objects_mock.TaskCollection.get_by_cluster_id.assert_called_once_with(
            cluster_id=cluster.id
        )
        objects_mock.TaskCollection.get_by_cluster_id.assert_called_once_with(
            cluster_id=cluster.id
        )
        objects_mock.TaskCollection.filter_by.assert_called_once_with(
            objects_mock.TaskCollection.get_by_cluster_id.return_value,
            name=self.manager.task_name
        )
        objects_mock.TaskCollection.filter_by_list.assert_called_once_with(
            objects_mock.TaskCollection.filter_by.return_value,
            'status',
            [consts.TASK_STATUSES.pending, consts.TASK_STATUSES.running]
        )
        objects_mock.TaskCollection.count.assert_called_once_with(
            objects_mock.TaskCollection.filter_by_list.return_value
        )
        objects_mock.TaskCollection.count.return_value = 1
        with self.assertRaises(manager.errors.DeploymentAlreadyStarted):
            self.manager._acquire_cluster()

    def test_is_node_for_redeploy(self, _):
        self.assertFalse(self.manager._is_node_for_redeploy(None))

        self.assertTrue(self.manager._is_node_for_redeploy(mock.MagicMock(
            pending_addition=True, status=consts.NODE_STATUSES.discover
        )))
        self.assertFalse(self.manager._is_node_for_redeploy(mock.MagicMock(
            pending_addition=False, status=consts.NODE_STATUSES.ready
        )))
        self.assertTrue(self.manager._is_node_for_redeploy(mock.MagicMock(
            pending_addition=True, status=consts.NODE_STATUSES.ready
        )))

    @mock.patch('nailgun.transactions.manager.objects')
    def test_get_tasks_if_no_legacy(self, objects_mock, _):
        cluster_obj = objects_mock.Cluster
        tasks = [
            {'id': 'tasks1', 'type': consts.ORCHESTRATOR_TASK_TYPES.puppet},
            {'id': 'tasks2', 'type': consts.ORCHESTRATOR_TASK_TYPES.group},
            {'id': 'tasks3', 'type': consts.ORCHESTRATOR_TASK_TYPES.shell},
            {'id': 'tasks4', 'type': consts.ORCHESTRATOR_TASK_TYPES.skipped}
        ]
        cluster_obj.get_deployment_tasks.return_value = tasks
        cluster_obj.is_propagate_task_deploy_enabled.return_value = False

        cluster = mock.MagicMock()
        result = self.manager._get_tasks(cluster, None, None, 'test')
        self.assertEqual(tasks, result)
        cluster_obj.get_deployment_tasks.assert_called_once_with(
            cluster, 'test'
        )
        cluster_obj.is_propagate_task_deploy_enabled.assert_called_once_with(
            cluster
        )

        filtered_result = self.manager._get_tasks(
            cluster, None, ['task2'], 'test'
        )
        tasks[2]['type'] = consts.ORCHESTRATOR_TASK_TYPES.skipped
        self.assertEqual(tasks, filtered_result)

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.legacy_tasks_adapter')
    def test_get_tasks_with_legacy(self, adapter_mock, objects_mock, _):
        cluster_obj = objects_mock.Cluster
        tasks = [
            {'id': 'tasks2', 'type': consts.ORCHESTRATOR_TASK_TYPES.group},
        ]
        cluster_obj.get_deployment_tasks.return_value = tasks
        cluster_obj.is_propagate_task_deploy_enabled.return_value = True
        adapter_mock.adapt_legacy_tasks.return_value = tasks

        cluster = mock.MagicMock()
        resolver = mock.MagicMock()
        result = self.manager._get_tasks(cluster, resolver, None, 'test')
        self.assertEqual(tasks, result)

        cluster_obj.is_propagate_task_deploy_enabled.assert_called_once_with(
            cluster
        )
        adapter_mock.adapt_legacy_tasks.assert_called_once_with(
            tasks, None, resolver
        )
        result2 = self.manager._get_tasks(
            cluster, resolver, None, consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE
        )
        self.assertEqual(tasks, result2)

        cluster_obj.get_legacy_plugin_tasks.assert_called_once_with(cluster)
        adapter_mock.adapt_legacy_tasks.assert_called_with(
            tasks, cluster_obj.get_legacy_plugin_tasks.return_value, resolver
        )

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.lcm')
    def test_assemble_astute_message(self, lcm_mock, obj_mock, _):
        resolver = mock.MagicMock()
        context = mock.MagicMock()
        tx = mock.MagicMock()
        tasks = mock.MagicMock()
        tasks_directory = mock.MagicMock()
        tasks_graph = mock.MagicMock()
        tasks_metadata = mock.MagicMock()

        lcm_mock.TransactionSerializer.serialize.return_value = (
            tasks_directory, tasks_graph, tasks_metadata
        )
        result = self.manager._assemble_astute_message(
            tx, context, tasks, resolver
        )
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
                }
            },
            result
        )
        lcm_mock.TransactionSerializer.serialize.assert_called_once_with(
            context, tasks, resolver
        )
        obj_mock.DeploymentHistoryCollection.create.assert_called_once_with(
            tx, tasks_graph
        )
