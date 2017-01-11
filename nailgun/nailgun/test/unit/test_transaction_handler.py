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

from nailgun import consts
from nailgun.db.sqlalchemy.models import Task
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun.test.base import BaseTestCase
from nailgun.utils import reverse


class TestTransactionHandlers(BaseTestCase):

    def setUp(self):
        super(TestTransactionHandlers, self).setUp()
        self.cluster_db = self.env.create(
            nodes_kwargs=[
                {"roles": ["controller"]}
            ]
        )

    def test_transaction_deletion(self):
        task = Task(
            name='deployment',
            cluster=self.cluster_db,
            status=consts.TASK_STATUSES.ready,
            progress=100
        )
        self.db.add(task)
        self.db.flush()
        resp = self.app.delete(
            reverse(
                'TransactionHandler',
                kwargs={'obj_id': task.id}
            ),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 204)
        resp = self.app.get(
            reverse(
                'TransactionHandler',
                kwargs={'obj_id': task.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)

    def test_running_transaction_deletion(self):
        task = Task(
            name='deployment',
            cluster=self.cluster_db,
            status=consts.TASK_STATUSES.running,
            progress=10
        )
        self.db.add(task)
        self.db.flush()
        resp = self.app.delete(
            reverse(
                'TransactionHandler',
                kwargs={'obj_id': task.id}
            ) + "?force=0",
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_forced_deletion_of_running_transaction_(self):
        task = Task(
            name='deployment',
            cluster=self.cluster_db,
            status=consts.TASK_STATUSES.running,
            progress=10
        )
        self.db.add(task)
        self.db.flush()

        resp = self.app.delete(
            reverse(
                'TransactionHandler',
                kwargs={'obj_id': task.id}
            ) + "?force=1",
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 204)
        resp = self.app.get(
            reverse(
                'TransactionHandler',
                kwargs={'obj_id': task.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)

    def test_hard_deletion_behavior(self):
        task = Task(
            name=consts.TASK_NAMES.deployment,
            cluster=self.cluster_db,
            status=consts.TASK_STATUSES.running,
            progress=10
        )
        self.db.add(task)
        self.db.flush()
        resp = self.app.delete(
            reverse(
                'TransactionHandler',
                kwargs={'obj_id': task.id}
            ) + "?force=1",
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 204)
        resp = self.app.get(
            reverse(
                'TransactionHandler',
                kwargs={'obj_id': task.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIsNone(self.db().query(Task).get(task.id))

    def test_get_transaction_cluster_attributes(self):
        cluster = self.cluster_db
        cluster_attrs = objects.Cluster.get_editable_attributes(cluster)
        transaction = objects.Transaction.create({
            'cluster_id': cluster.id,
            'status': consts.TASK_STATUSES.ready,
            'name': consts.TASK_NAMES.deployment
        })
        objects.Transaction.attach_cluster_settings(
            transaction, {'editable': cluster_attrs}
        )
        self.assertIsNotNone(
            objects.Transaction.get_cluster_settings(transaction)
        )
        resp = self.app.get(
            reverse(
                'TransactionClusterSettings',
                kwargs={'transaction_id': transaction.id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.datadiff(cluster_attrs, resp.json_body['editable'])

    def test_get_cluster_attributes_fail_not_existed_transaction(self):
        resp = self.app.get(
            reverse(
                'TransactionClusterSettings',
                kwargs={'transaction_id': -1}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_transaction_deployment_info(self):
        cluster = self.cluster_db
        nodes = objects.Cluster.get_nodes_not_for_deletion(cluster)
        deployment_info = deployment_serializers.serialize_for_lcm(
            cluster, nodes
        )
        deployment_info['nodes'] = {
            n['uid']: n for n in deployment_info['nodes']
        }
        transaction = objects.Transaction.create({
            'cluster_id': cluster.id,
            'status': consts.TASK_STATUSES.ready,
            'name': consts.TASK_NAMES.deployment
        })
        objects.Transaction.attach_deployment_info(
            transaction, deployment_info
        )
        self.assertIsNotNone(
            objects.Transaction.get_deployment_info(transaction)
        )
        resp = self.app.get(
            reverse(
                'TransactionDeploymentInfo',
                kwargs={'transaction_id': transaction.id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.datadiff(deployment_info, resp.json_body)

    def test_get_deployment_info_fail_not_existed_transaction(self):
        resp = self.app.get(
            reverse(
                'TransactionDeploymentInfo',
                kwargs={'transaction_id': -1}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_transaction_network_settings(self):
        cluster = self.cluster_db
        resp = self.env.neutron_networks_get(cluster.id)
        self.assertEqual(200, resp.status_code)
        net_attrs = resp.json_body
        transaction = objects.Transaction.create({
            'cluster_id': cluster.id,
            'status': consts.TASK_STATUSES.ready,
            'name': consts.TASK_NAMES.deployment
        })
        objects.Transaction.attach_network_settings(transaction, net_attrs)
        self.assertIsNotNone(
            objects.Transaction.get_network_settings(transaction)
        )
        resp = self.app.get(
            reverse(
                'TransactionNetworkSettings',
                kwargs={'transaction_id': transaction.id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.datadiff(net_attrs, resp.json_body)

    def test_get_network_settings_fail_not_existed_transaction(self):
        resp = self.app.get(
            reverse(
                'TransactionNetworkSettings',
                kwargs={'transaction_id': -1}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)


class TestTransactionCollectionHandlers(BaseTestCase):

    def setUp(self):
        super(TestTransactionCollectionHandlers, self).setUp()

        self.cluster1 = self.env.create(
            nodes_kwargs=[
                {"roles": ["controller"]}
            ]
        )
        self.cluster2 = self.env.create(
            nodes_kwargs=[
                {"roles": ["controller"]}
            ]
        )

        self.tasks = [{'name': 'deployment',
                       'cluster': self.cluster1,
                       'status': consts.TASK_STATUSES.ready,
                       'progress': 100},
                      {'name': 'provision',
                       'cluster': self.cluster1,
                       'status': consts.TASK_STATUSES.ready,
                       'progress': 100},
                      {'name': 'deployment',
                       'cluster': self.cluster1,
                       'status': consts.TASK_STATUSES.running,
                       'progress': 100},
                      {'name': 'deployment',
                       'cluster': self.cluster2,
                       'status': consts.TASK_STATUSES.ready,
                       'progress': 100}]

        task_objs = []
        for task in self.tasks:
            task_obj = objects.Transaction.create(task)
            self.db.add(task_obj)
            task_objs.append(task_obj)
            task['cluster'] = task['cluster'].id
        self.db.flush()

        for i, task in enumerate(self.tasks):
            task['uuid'] = task_objs[i].uuid

    def _compare_task_uuids(self, expected, actual):
        actual_uuids = [task['uuid'] for task in actual]
        expected_uuids = [task['uuid'] for task in expected]
        self.assertItemsEqual(actual_uuids, expected_uuids)

    def test_transactions_get_all(self):
        resp = self.app.get(
            reverse(
                'TransactionCollectionHandler',
            ),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self._compare_task_uuids(self.tasks, resp.json_body)

    def test_transactions_get_by_cluster(self):
        resp = self.app.get(
            reverse(
                'TransactionCollectionHandler',
            ) + "?cluster_id={0}".format(self.cluster2.id),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self._compare_task_uuids([self.tasks[3]], resp.json_body)

    def test_transactions_get_by_status(self):
        resp = self.app.get(
            reverse(
                'TransactionCollectionHandler',
            ) + "?statuses=running",
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self._compare_task_uuids([self.tasks[2]], resp.json_body)

        resp = self.app.get(
            reverse(
                'TransactionCollectionHandler',
            ) + "?statuses=running,ready",
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self._compare_task_uuids(self.tasks, resp.json_body)

    def test_transactions_get_by_task_name(self):
        resp = self.app.get(
            reverse(
                'TransactionCollectionHandler',
            ) + "?transaction_types=provision",
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self._compare_task_uuids([self.tasks[1]], resp.json_body)

        resp = self.app.get(
            reverse(
                'TransactionCollectionHandler',
            ) + "?transaction_types=provision,deployment",
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self._compare_task_uuids(self.tasks, resp.json_body)

    def test_transactions_get_invalid_status(self):
        resp = self.app.get(
            reverse(
                'TransactionCollectionHandler',
            ) + "?statuses=invalid",
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Statuses parameter could only be',
                      resp.json_body['message'])

    def test_transactions_get_invalid_task_name(self):
        resp = self.app.get(
            reverse(
                'TransactionCollectionHandler',
            ) + "?transaction_types=invalid",
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Transaction types parameter could only be',
                      resp.json_body['message'])
