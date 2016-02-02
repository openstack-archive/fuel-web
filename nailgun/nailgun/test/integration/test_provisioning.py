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

from nailgun import consts
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
                {"api": False, "status": consts.NODE_STATUSES.ready},
                {"api": False, "pending_addition": True,
                 "roles": ["compute"]},
                {"api": False, "status": consts.NODE_STATUSES.provisioning,
                 "roles": ["compute"],
                 "pending_addition": True},
                {"api": False, "status": consts.NODE_STATUSES.deploying,
                 "roles": ["compute"],
                 "pending_addition": True},
                {"api": False, "status": consts.NODE_STATUSES.error,
                 "roles": ["compute"],
                 "error_type": "deploy"},
                {"api": False, "status": consts.NODE_STATUSES.error,
                 "roles": ["compute"],
                 "error_type": "provision"}
            ]
        )
        cluster = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster)
        self.env.network_manager.assign_ips(
            cluster, self.env.nodes, consts.NETWORKS.fuelweb_admin
        )
        self.env.network_manager.assign_ips(
            cluster, self.env.nodes, consts.NETWORKS.management
        )
        self.env.network_manager.assign_ips(
            cluster, self.env.nodes, consts.NETWORKS.storage
        )
        self.env.network_manager.assign_ips(
            cluster, self.env.nodes, consts.NETWORKS.public
        )

        self.env.launch_deployment()

        self.env.refresh_nodes()
        self.assertEqual(
            self.env.nodes[0].status, consts.NODE_STATUSES.ready
        )
        self.assertEqual(
            self.env.nodes[1].status, consts.NODE_STATUSES.provisioning
        )
        self.assertEqual(
            self.env.nodes[2].status, consts.NODE_STATUSES.provisioning
        )
        self.assertEqual(
            self.env.nodes[3].status, consts.NODE_STATUSES.provisioning
        )
        self.assertEqual(
            self.env.nodes[4].status, consts.NODE_STATUSES.error
        )
        self.assertEqual(
            self.env.nodes[5].status, consts.NODE_STATUSES.provisioning
        )

    @fake_tasks()
    def test_node_has_proper_status_after_provisioning(self, *_):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False, "status": consts.NODE_STATUSES.discover,
                 "roles": ["compute"]},
                {"api": False, "roles": ["controller"],
                 "status": consts.NODE_STATUSES.discover}
            ]
        )
        cluster_db = self.env.clusters[-1]
        self.env.network_manager.assign_ips(
            cluster_db, self.env.nodes, consts.NETWORKS.fuelweb_admin
        )
        self.env.network_manager.assign_ips(
            cluster_db, self.env.nodes, consts.NETWORKS.management
        )
        self.env.network_manager.assign_ips(
            cluster_db, self.env.nodes, consts.NETWORKS.storage
        )
        self.env.network_manager.assign_ips(
            cluster_db, self.env.nodes, consts.NETWORKS.public
        )

        task = self.env.launch_provisioning_selected(cluster_id=cluster_db.id)
        self.env.wait_ready(task, timeout=120)

        for n in cluster_db.nodes:
            self.assertEqual(consts.NODE_STATUSES.provisioned, n.status)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_vms_reset_on_provisioning(self, mocked_rpc=None):
        self.env.create(
            nodes_kwargs=[
                {
                    'api': False,
                    'roles': ['virt'],
                    'status': consts.NODE_STATUSES.ready
                },
                {'api': False, 'roles': ['virt']},
            ]
        )

        nodes = self.env.nodes
        nodes[0].attributes.vms_conf = [
            {'id': 1, 'cpu': 1, 'mem': 2, 'created': True},
            {'id': 2, 'cpu': 1, 'mem': 2, 'created': True}
        ]
        nodes[1].attributes.vms_conf = [
            {'id': 1, 'cpu': 2, 'mem': 4}
        ]
        self.db.commit()

        self.env.launch_provisioning_selected([str(nodes[0].id)])

        for conf in nodes[0].attributes.vms_conf:
            self.assertFalse(conf['created'])
