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

import json

from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestNodeGroups(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeGroups, self).setUp()
        self.cluster = self.env.create_cluster(api=False)

    def create_node_group(self):
        resp = self.app.post(
            reverse('NodeGroupCollectionHandler'),
            json.dumps({'cluster_id': self.cluster['id'], 'name': 'test_ng'}),
            headers=self.default_headers,
            expect_errors=False
        )

        return resp

    def test_nodegroup_creation(self):
        resp = self.create_node_group()

        self.assertEquals(resp.status_code, 201)
        response = json.loads(resp.body)
        self.assertEquals(response['cluster'], self.cluster['id'])

    def test_nodegroup_assignment(self):
        self.env.create(
            cluster_kwargs={'api': True},
            nodes_kwargs=[{
                'roles': [],
                'pending_roles': ['controller'],
                'pending_addition': True,
                'api': True}]
        )
        cluster = self.env.clusters[0]
        node = self.env.nodes[0]

        resp = self.app.post(
            reverse('NodeGroupCollectionHandler'),
            json.dumps({'cluster_id': cluster['id'], 'name': 'test_ng'}),
            headers=self.default_headers,
            expect_errors=False
        )

        response = json.loads(resp.body)
        ng_id = response['id']

        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node['id']}),
            json.dumps({'group_id': ng_id}),
            headers=self.default_headers,
            expect_errors=False
        )

        response = json.loads(resp.body)
        self.assertEquals(resp.status_code, 200)
        self.assertEquals(node.group_id, ng_id)

    def test_nodegroup_create_network(self):
        resp = self.create_node_group()

        response = json.loads(resp.body)
        nets = db().query(NetworkGroup).filter_by(group_id=response['id'])
        self.assertEquals(nets.count(), 5)

    def test_nodegroup_deletion(self):
        resp = self.create_node_group()
        response = json.loads(resp.body)
        group_id = response['id']

        self.app.delete(
            reverse(
                'NodeGroupHandler',
                kwargs={'obj_id': group_id}
            ),
            headers=self.default_headers,
            expect_errors=False
        )

        nets = db().query(NetworkGroup).filter_by(group_id=response['id'])
        self.assertEquals(nets.count(), 0)
