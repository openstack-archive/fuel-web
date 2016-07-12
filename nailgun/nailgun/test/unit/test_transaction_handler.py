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

from nailgun import consts
from nailgun.db.sqlalchemy.models import Task
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun.test.base import BaseTestCase
from nailgun.test.base import mock_rpc
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
