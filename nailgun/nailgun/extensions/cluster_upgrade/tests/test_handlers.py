# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

from mock import patch

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.test import base
from nailgun.utils import reverse


class TestNodeReassignHandler(base.BaseIntegrationTest):

    @patch('nailgun.task.task.rpc.cast')
    def test_node_reassign_handler(self, mcast):
        self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'status': consts.NODE_STATUSES.ready}])
        cluster = self.env.clusters[0]

        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': cluster['id']}),
            jsonutils.dumps({'node_id': cluster.nodes[0]['id']}),
            headers=self.default_headers)
        self.assertEqual(202, resp.status_code)

    @patch('nailgun.task.task.rpc.cast')
    def test_node_reassign_handler_no_node(self, mcast):
        self.env.create_cluster()

        cluster = self.env.clusters[0]

        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': cluster['id']}),
            jsonutils.dumps({'node_id': 42}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(404, resp.status_code)
        self.assertEqual("Node with id 42 was not found",
                         resp.json_body['message'])

    @patch('nailgun.task.task.rpc.cast')
    def test_node_reassing_handler_wrong_status(self, mcast):
        self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'status': 'discover'}])
        cluster = self.env.clusters[0]

        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': cluster['id']}),
            jsonutils.dumps({'node_id': cluster.nodes[0]['id']}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual("Node should be in ready state",
                         resp.json_body['message'])
