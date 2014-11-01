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

from mock import patch

from nailgun import objects

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class TestProvisioning(BaseIntegrationTest):

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_nodes_in_cluster(self, mocked_rpc):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False, "pending_addition": True},
                {"api": False, "cluster_id": None}
            ]
        )
        cluster_db = self.env.clusters[0]
        map(cluster_db.nodes.append, self.env.nodes[:2])
        self.db.add(cluster_db)
        self.db.commit()

        self.assertEqual(len(cluster_db.nodes), 2)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_node_status_changes_to_provision(self, mocked_rpc=None):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False, "status": "ready"},
                {"api": False, "pending_addition": True,
                 "roles": ["compute"]},
                {"api": False, "status": "provisioning",
                 "roles": ["compute"],
                 "pending_addition": True},
                {"api": False, "status": "deploying",
                 "roles": ["compute"],
                 "pending_addition": True},
                {"api": False, "status": "error",
                 "roles": ["compute"],
                 "error_type": "deploy"},
                {"api": False, "status": "error",
                 "roles": ["compute"],
                 "error_type": "provision"}
            ]
        )
        cluster = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster)
        self.env.network_manager.assign_ips(self.env.nodes, 'fuelweb_admin')
        self.env.network_manager.assign_ips(self.env.nodes, 'management')
        self.env.network_manager.assign_ips(self.env.nodes, 'storage')
        self.env.network_manager.assign_ips(self.env.nodes, 'public')

        self.env.launch_deployment()

        self.env.refresh_nodes()
        self.assertEqual(self.env.nodes[0].status, 'ready')
        self.assertEqual(self.env.nodes[1].status, 'provisioning')
        self.assertEqual(self.env.nodes[2].status, 'provisioning')
        self.assertEqual(self.env.nodes[3].status, 'provisioning')
        self.assertEqual(self.env.nodes[4].status, 'error')
        self.assertEqual(self.env.nodes[5].status, 'provisioning')
