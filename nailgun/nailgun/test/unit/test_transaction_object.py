# -*- coding: utf-8 -*-

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

from nailgun.test.base import BaseTestCase

from nailgun import consts
from nailgun import objects


class TestTransactionObject(BaseTestCase):
    def setUp(self):
        super(TestTransactionObject, self).setUp()
        self.cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['compute']},
                {'roles': ['cinder']}])

    def test_get_last_success_run(self):
        objects.Transaction.create({
            'cluster_id': self.cluster.id,
            'name': consts.TASK_NAMES.deployment,
            'status': consts.TASK_STATUSES.pending
        })
        objects.Transaction.create({
            'cluster_id': self.cluster.id,
            'name': consts.TASK_NAMES.deployment,
            'status': consts.TASK_STATUSES.error
        })
        transaction = objects.TransactionCollection.get_last_succeed_run(
            self.cluster
        )
        self.assertIsNone(transaction)
        objects.Transaction.create({
            'cluster_id': self.cluster.id,
            'name': consts.TASK_NAMES.deployment,
            'status': consts.TASK_STATUSES.ready
        })
        finished2 = objects.Transaction.create({
            'cluster_id': self.cluster.id,
            'name': consts.TASK_NAMES.deployment,
            'status': consts.TASK_STATUSES.ready
        })
        transaction = objects.TransactionCollection.get_last_succeed_run(
            self.cluster
        )
        self.assertEqual(finished2.id, transaction.id)

    def test_get_deployment_info(self):
        transaction = objects.Transaction.create({
            'cluster_id': self.cluster.id,
            'name': consts.TASK_NAMES.deployment,
            'status': consts.TASK_STATUSES.ready
        })
        self.assertEqual(
            objects.Transaction.get_deployment_info(transaction),
            {}
        )
        info = {'common': {'a': 'b'},
                'nodes': {'7': {'test': {'test': 'test'}}}}
        objects.Transaction.attach_deployment_info(transaction, info)
        self.assertEqual(
            info, objects.Transaction.get_deployment_info(transaction)
        )
        self.assertEqual(objects.Transaction.get_deployment_info(None), {})

    def test_get_cluster_settings(self):
        transaction = objects.Transaction.create({
            'cluster_id': self.cluster.id,
            'name': consts.TASK_NAMES.deployment,
            'status': consts.TASK_STATUSES.ready
        })
        self.assertIsNone(
            objects.Transaction.get_cluster_settings(transaction)
        )
        info = {'test': 'test'}
        objects.Transaction.attach_cluster_settings(transaction, info)
        self.assertEqual(
            info, objects.Transaction.get_cluster_settings(transaction)
        )
        self.assertIsNone(objects.Transaction.get_cluster_settings(None))

    def test_get_network_settings(self):
        transaction = objects.Transaction.create({
            'cluster_id': self.cluster.id,
            'name': consts.TASK_NAMES.deployment,
            'status': consts.TASK_STATUSES.ready
        })
        self.assertIsNone(
            objects.Transaction.get_network_settings(transaction)
        )
        info = {'test': 'test'}
        objects.Transaction.attach_network_settings(transaction, info)
        self.assertEqual(
            info, objects.Transaction.get_network_settings(transaction)
        )
        self.assertIsNone(objects.Transaction.get_network_settings(None))

    def test_get_successful_transactions_per_task(self):
        history_collection = objects.DeploymentHistoryCollection
        get_succeed = (
            objects.TransactionCollection.get_successful_transactions_per_task
        )
        uid1 = '1'
        uid2 = '2'

        tasks_graph = {
            None: [
                {'id': 'post_deployment_start'},
                {'id': 'post_deployment_end'}
            ],
            uid1: [{'id': 'dns-client'}]
        }

        def make_task_with_history(task_status, graph):
            task = self.env.create_task(
                name=consts.TASK_NAMES.deployment,
                status=task_status,
                cluster_id=self.cluster.id)

            history_collection.create(task, graph)

            history_collection.all().update(
                {'status': consts.HISTORY_TASK_STATUSES.ready})
            return task

        # create some tasks in history
        task1 = make_task_with_history('ready', tasks_graph)
        transactions = get_succeed(self.cluster.id, ['dns-client']).all()
        self.assertEqual(transactions, [(task1, uid1, 'dns-client')])

        # remove 'dns-client' and add 'test' to graph for two nodes
        tasks_graph[uid1] = tasks_graph[uid2] = [{'id': 'test'}]
        task2 = make_task_with_history('ready', tasks_graph)
        transactions = get_succeed(self.cluster.id, ['test']).all()
        self.assertEqual(transactions, [(task2, uid1, 'test'),
                                        (task2, uid2, 'test')])

        # remove 'test' and add 'dns-client' to graph, leave node2 as previous
        tasks_graph[uid1] = [{'id': 'dns-client'}]
        task3 = make_task_with_history('ready', tasks_graph)
        transactions = get_succeed(self.cluster.id,
                                   ['dns-client', 'test']).all()

        # now we should find both `test` and `dns-client` transactions
        # on node 1 and onle `test` on node 2
        self.assertEqual(
            transactions,
            [(task3, uid1, 'dns-client'),
             (task2, uid1, 'test'),
             (task3, uid2, 'test')]
        )

        # filter out node 2
        transactions = get_succeed(self.cluster.id,
                                   ['dns-client', 'test'], {uid1: {}}).all()
        self.assertEqual(
            transactions,
            [(task3, uid1, 'dns-client'),
             (task2, uid1, 'test')]
        )
