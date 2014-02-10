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
                'cluster_id': cluster.id,
                'id': node.id,
                'roles': ['controller']
            }
        ]
        resp = self.app.post(
            reverse('NodeAssignmentHandler'),
            json.dumps(assignment_data),
            headers=self.default_headers
        )
        self.assertEquals(201, resp.status)
        self.assertEqual(node.cluster, cluster)
        self.datadiff(node.pending_roles, assignment_data[0]['roles'])

        resp = self.app.post(
            reverse('NodeAssignmentHandler'),
            json.dumps(assignment_data),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(400, resp.status)

    def test_unassignment(self):
        self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[{}]
        )
        node = self.env.nodes[0]
        resp = self.app.delete(
            reverse('NodeAssignmentHandler')
            + '?nodes={0}'.format(node.id),
            headers=self.default_headers
        )
        self.assertEquals(204, resp.status)
        self.assertEqual(node.cluster, None)
        self.assertEqual(node.pending_roles, [])

        for node_ids in ("", str(node.id + 50)):
            resp = self.app.delete(
                reverse('NodeAssignmentHandler')
                + '?nodes={0}'.format(node_ids),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEquals(404, resp.status)
