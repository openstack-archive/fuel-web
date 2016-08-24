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

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.lcm')
    def test_make_astute_message(self, lcm_mock, obj_mock):
        resolver = mock.MagicMock()
        context = mock.MagicMock()
        tx = mock.MagicMock(dry_run=False, noop_run=False,
                            cache={'dry_run': False, 'noop_run': False})
        tasks = mock.MagicMock()
        tasks_directory = mock.MagicMock()
        tasks_graph = mock.MagicMock()
        tasks_metadata = mock.MagicMock()

        lcm_mock.TransactionSerializer.serialize.return_value = (
            tasks_directory, tasks_graph, tasks_metadata
        )

        result = manager.make_astute_message(tx, context, tasks, resolver)
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
        objects_mock.TaskCollection.get_cluster_tasks.assert_called_once_with(
            cluster.id
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
                progress=0, status=consts.NODE_STATUSES.ready
            ))
        )
        self.assertTrue(
            manager._is_node_for_redeploy(mock.MagicMock(
                pending_addition=False, status=consts.NODE_STATUSES.stopped,
                progress=0, error_type=None
            ))
        )


class TestGetTasksToRun(BaseUnitTest):

    @mock.patch('nailgun.transactions.manager.objects')
    def test_get_tasks_if_no_legacy(self, objects_mock):
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
        result = manager._get_tasks_to_run(cluster, 'test', None, None)
        self.assertEqual(tasks, result)
        cluster_obj.get_deployment_tasks.assert_called_once_with(
            cluster, 'test'
        )
        cluster_obj.is_propagate_task_deploy_enabled.assert_called_once_with(
            cluster
        )

        filtered_result = manager._get_tasks_to_run(
            cluster, 'test', None, ['task2']
        )
        tasks[2]['type'] = consts.ORCHESTRATOR_TASK_TYPES.skipped
        self.assertEqual(tasks, filtered_result)

    @mock.patch('nailgun.transactions.manager.objects')
    @mock.patch('nailgun.transactions.manager.legacy_tasks_adapter')
    def test_get_tasks_with_legacy(self, adapter_mock, objects_mock):
        cluster_obj = objects_mock.Cluster
        tasks = [
            {'id': 'tasks2', 'type': consts.ORCHESTRATOR_TASK_TYPES.group},
        ]
        cluster_obj.get_deployment_tasks.return_value = tasks
        cluster_obj.is_propagate_task_deploy_enabled.return_value = True
        adapter_mock.adapt_legacy_tasks.return_value = tasks

        cluster = mock.MagicMock()
        resolver = mock.MagicMock()
        result = manager._get_tasks_to_run(cluster, 'test', resolver, None)
        self.assertEqual(tasks, result)

        cluster_obj.is_propagate_task_deploy_enabled.assert_called_once_with(
            cluster
        )
        adapter_mock.adapt_legacy_tasks.assert_called_once_with(
            tasks, None, resolver
        )
        result2 = manager._get_tasks_to_run(
            cluster, consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE, resolver, None,
        )
        self.assertEqual(tasks, result2)

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
        transaction = mock.MagicMock(dry_run=True, noop_run=False)
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
