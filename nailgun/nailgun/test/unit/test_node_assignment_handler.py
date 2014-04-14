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

import json

from nailgun import consts
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestAssignmentHandlers(BaseIntegrationTest):
    def test_assignment(self):
        self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[
                {"cluster_id": None}
            ]
        )
        cluster = self.env.clusters[0]
        node = self.env.nodes[0]
        assignment_data = [
            {
                "id": node.id,
                "roles": ['controller']
            }
        ]
        resp = self.app.post(
            reverse(
                'NodeAssignmentHandler',
                kwargs={'cluster_id': cluster.id}
            ),
            json.dumps(assignment_data),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        self.assertEqual(node.cluster, cluster)
        self.datadiff(
            node.pending_roles,
            assignment_data[0]["roles"]
        )

        resp = self.app.post(
            reverse(
                'NodeAssignmentHandler',
                kwargs={'cluster_id': cluster.id}
            ),
            json.dumps(assignment_data),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(400, resp.status_code)

    def test_unassignment(self):
        cluster = self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[{}]
        )
        node = self.env.nodes[0]
        # correct unassignment
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            json.dumps([{'id': node.id}]),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(node.cluster, None)
        self.assertEqual(node.pending_roles, [])

        #Test with invalid node ids
        for node_id in (0, node.id + 50):
            resp = self.app.post(
                reverse(
                    'NodeUnassignmentHandler',
                    kwargs={'cluster_id': cluster['id']}
                ),
                json.dumps([{'id': node_id}]),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(400, resp.status_code)
        #Test with invalid cluster id
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster['id'] + 5}
            ),
            json.dumps([{'id': node.id}]),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)

        # Test with wrong cluster id
        self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[{}]
        )

        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            json.dumps([{'id': self.env.clusters[1].nodes[0].id}]),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_unassignment_after_deploy(self):
        cluster = self.env.create(
            nodes_kwargs=[{}]
        )
        node = self.env.nodes[0]
        node.status = 'error'
        self.db.commit()
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            json.dumps([{'id': node.id}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(node.pending_deletion, True)

    def _assign_node(self, cluster, data, expected_status=200):
        resp = self.app.post(
            reverse(
                'NodeAssignmentHandler',
                kwargs={'cluster_id': cluster.id}
            ),
            json.dumps(data),
            headers=self.default_headers,
            expect_errors=(expected_status != 200)
        )
        self.assertEquals(expected_status, resp.status_code)

    def _unassign_node(self, cluster, data, expected_status=200):
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster.id}
            ),
            json.dumps([{'id': d['id']} for d in data]),
            headers=self.default_headers,
            expect_errors=(expected_status != 200)
        )
        self.assertEquals(expected_status, resp.status_code)

    def test_roles_assignment(self):
        self.env.create_release(roles='')
        self.env.create_node(api=True)
        self.env.create_node(api=True)
        self.env.create(
            cluster_kwargs={'api': True},
            nodes_kwargs=[{'cluster_id': None}]
        )
        cluster = self.env.clusters[0]
        node_0 = self.env.nodes[0]
        node_1 = self.env.nodes[1]
        data_sets = [
            ([{'id': node_0.id,
               'roles': [consts.ROLE_CONTROLLER]}], 200),
            ([{'id': node_0.id,
               'roles': [consts.ROLE_CONTROLLER]},
              {'id': node_1.id,
               'roles': [consts.ROLE_COMPUTE]}], 200),
            ([{'id': node_0.id,
               'roles': [consts.ROLE_COMPUTE, consts.ROLE_CINDER]}], 200),
            ([{'id': node_0.id,
               'roles': [consts.ROLE_CONTROLLER, consts.ROLE_COMPUTE]}], 400)
        ]

        nodes_idx = dict([(node.id, node) for node in self.env.nodes])
        for data, exp_status in data_sets:
            self._assign_node(cluster, data, expected_status=exp_status)
            for node_data in data:
                node = nodes_idx[node_data['id']]
                self.datadiff(node.pending_roles, node_data['roles'])
            self._unassign_node(cluster, data, expected_status=exp_status)
