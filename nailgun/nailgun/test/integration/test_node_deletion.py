# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import logging

from nailgun import consts
from nailgun import objects

from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse

logger = logging.getLogger(__name__)


class TestNodeDeletion(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeDeletion, self).setUp()
        self.env.create(nodes_kwargs=[{"pending_addition": True}])
        self.cluster = self.env.clusters[0]
        self.node_ids = [node.id for node in self.cluster.nodes]

    @fake_tasks()
    def test_node_deletion_and_attributes_clearing(self, _):
        node_id = self.node_ids[0]

        resp = self.app.delete(
            reverse(
                'NodeHandler',
                kwargs={'obj_id': node_id}),
            headers=self.default_headers
        )
        # @fake_tasks runs synchoronously, so nodes are removed
        # that's why API returns 200, not 202
        self.assertEqual(200, resp.status_code)
        task = objects.Task.get_by_uuid(resp.json_body['uuid'])
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

        node_try = self.db.query(Node).filter_by(
            cluster_id=self.cluster.id
        ).first()
        self.assertIsNone(node_try)

        management_net = self.db.query(NetworkGroup).\
            filter(NetworkGroup.group_id ==
                   objects.Cluster.get_default_group(self.cluster).id).\
            filter_by(name='management').first()

        ipaddrs = self.db.query(IPAddr).\
            filter_by(node=node_id).all()

        self.assertEqual(list(management_net.nodes), [])
        self.assertEqual(list(ipaddrs), [])

    @fake_tasks()
    def test_batch_node_deletion_and_attributes_clearing(self, _):
        url = reverse('NodeCollectionHandler')
        query_str = 'ids={0}'.format(','.join(map(str, self.node_ids)))

        resp = self.app.delete(
            '{0}?{1}'.format(url, query_str),
            headers=self.default_headers
        )
        # @fake_tasks runs synchoronously, so nodes are removed
        # that's why API returns 200, not 202
        self.assertEqual(200, resp.status_code)
        task = objects.Task.get_by_uuid(resp.json_body['uuid'])
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

        node_query = self.db.query(Node).filter_by(cluster_id=self.cluster.id)
        self.assertEquals(node_query.count(), 0)

    @fake_tasks(fake_rpc=False, mock_rpc=True)
    def test_mclient_remove_is_false_on_node_deletion(self, mrpc):
        url = reverse(
            'NodeHandler',
            kwargs={'obj_id': self.node_ids[0]}
        )

        self.app.delete(
            url,
            headers=self.default_headers
        )

        msg = mrpc.call_args[0][1]

        self.assertTrue(
            all([node['mclient_remove'] is False
                 for node in msg['args']['nodes']])
        )

    @fake_tasks(fake_rpc=False, mock_rpc=True)
    def test_mclient_remove_is_false_on_node_collection_deletion(self, mrpc):
        url = reverse('NodeCollectionHandler')
        query_str = 'ids={0}'.format(','.join(map(str, self.node_ids)))

        self.app.delete(
            '{0}?{1}'.format(url, query_str),
            headers=self.default_headers
        )

        msg = mrpc.call_args[0][1]

        self.assertTrue(
            all([node['mclient_remove'] is False
                 for node in msg['args']['nodes']])
        )


class TestNodeDeletionBadRequest(BaseIntegrationTest):

    def test_node_handlers_deletion_bad_request(self):
        self.env.create(nodes_kwargs=[
            {'roles': ['controller'], 'status': consts.NODE_STATUSES.error}
        ])
        cluster_db = self.env.clusters[0]

        node_to_delete = self.env.create_node(
            cluster_id=cluster_db.id,
            roles=['controller'],
            status=consts.NODE_STATUSES.ready
        )

        err_msg = ("One of the cluster controllers is in error state, "
                   "please, eliminate the problem prior to proceeding further")

        resp = self.app.delete(
            reverse(
                'NodeHandler',
                kwargs={'obj_id': node_to_delete.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn(err_msg, resp.body)

        url = reverse('NodeCollectionHandler')
        query_str = 'ids={0}'.format(node_to_delete.id)
        resp = self.app.delete(
            '{0}?{1}'.format(url, query_str),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn(err_msg, resp.body)
