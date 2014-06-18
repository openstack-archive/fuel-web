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

from nailgun.db.sqlalchemy.models import NodeBondInterface

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


class TestClusterStateUnassigment(BaseIntegrationTest):

    def test_delete_bond_and_networks_state_on_unassigmnet(self):
        """Test verifies that
        1. bond configuration will be deleted
        2. network unassigned from node interfaces
        when node unnasigned from cluster
        """
        cluster = self.env.create(
            nodes_kwargs=[{}]
        )
        node = self.env.nodes[0]
        node.bond_interfaces.append(
            NodeBondInterface(name='ovs-bond0',
                              slaves=node.nic_interfaces))
        self.db.flush()
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            json.dumps([{'id': node.id}]),
            headers=self.default_headers
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(node.bond_interfaces, [])
        for interface in node.interfaces:
            self.assertEqual(interface.assigned_networks_list, [])
