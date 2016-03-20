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

from nailgun import consts
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class TestCluster(BaseIntegrationTest):

    def check_no_primary_node(self, cluster, roles):
        self.assertIsInstance(roles, (tuple, list))
        for role in roles:
            self.assertIsNone(objects.Cluster.get_primary_node(
                cluster, role))

    def check_has_primary_node(self, cluster, roles):
        self.assertIsInstance(roles, (tuple, list))
        for role in roles:
            primary_node = objects.Cluster.get_primary_node(
                cluster, role)
            self.assertIsNotNone(primary_node)

    def test_adjust_nodes_lists_on_controller_removing(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'pending_roles': ['controller']},
                {'roles': ['controller']},
                {'roles': ['controller']},
                {'roles': ['compute']},
            ]
        )
        cluster = self.env.clusters[0]
        controllers = filter(lambda x: 'controller' in x.all_roles,
                             cluster.nodes)

        n_delete = []
        n_deploy = []
        objects.Cluster.adjust_nodes_lists_on_controller_removing(
            cluster, n_delete, n_deploy)
        self.assertItemsEqual([], n_delete)
        self.assertItemsEqual([], n_deploy)

        n_delete = controllers
        n_deploy = []
        objects.Cluster.adjust_nodes_lists_on_controller_removing(
            cluster, n_delete, n_deploy)
        self.assertItemsEqual(controllers, n_delete)
        self.assertItemsEqual([], n_deploy)

        n_delete = controllers[:1]
        n_deploy = []
        objects.Cluster.adjust_nodes_lists_on_controller_removing(
            cluster, n_delete, n_deploy)
        self.assertItemsEqual(controllers[:1], n_delete)
        self.assertItemsEqual(controllers[1:], n_deploy)

        n_delete = controllers[:1]
        n_deploy = controllers[2:]
        objects.Cluster.adjust_nodes_lists_on_controller_removing(
            cluster, n_delete, n_deploy)
        self.assertItemsEqual(controllers[:1], n_delete)
        self.assertItemsEqual(controllers[1:], n_deploy)

    def test_adjust_nodes_lists_on_controller_removing_no_cluster(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']}
            ]
        )
        cluster = self.env.clusters[0]

        for node in cluster.nodes:
            self.assertIn('controller', node.all_roles)
        objects.Cluster.adjust_nodes_lists_on_controller_removing(
            cluster, cluster.nodes, [])
        self.assertNotRaises(
            AttributeError,
            objects.Cluster.adjust_nodes_lists_on_controller_removing,
            cluster, cluster.nodes, [])

    @fake_tasks(override_state={'progress': 100,
                                'status': consts.TASK_STATUSES.ready})
    def test_get_primary_node(self):
        self.env.create(
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'pending_addition': True},
                {'pending_roles': ['controller'],
                 'pending_addition': True},
                {'pending_roles': ['compute'],
                 'pending_addition': True},
                {'pending_roles': ['compute'],
                 'pending_addition': True},
            ]
        )
        cluster = self.env.clusters[0]

        # Checking no primary nodes before deployment
        self.check_no_primary_node(
            cluster, ('controller', 'compute', 'fake_role'))

        # Checking primary nodes after deployment
        deploy = self.env.launch_deployment()
        self.assertEqual(deploy.status, consts.TASK_STATUSES.ready)

        self.check_has_primary_node(cluster, ('controller',))
        self.check_no_primary_node(cluster, ('compute', 'fake_role'))

    @fake_tasks(override_state={'progress': 100,
                                'status': consts.TASK_STATUSES.ready})
    def test_get_primary_node_pending_deletion(self):
        self.env.create(
            api=True,
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True}
            ]
        )
        cluster = self.env.clusters[0]

        # Checking primary present
        deploy = self.env.launch_deployment()
        self.assertEqual(deploy.status, consts.TASK_STATUSES.ready)

        self.check_has_primary_node(cluster, ('controller',))
        self.check_no_primary_node(cluster, ('compute', 'fake_role'))

        # Checking no primary for pending deleting nodes
        primary_controller = objects.Cluster.get_primary_node(
            cluster, 'controller')
        primary_controller.pending_deletion = True
        self.env.db().flush()

        self.check_no_primary_node(
            cluster, ('controller', 'compute', 'fake_role'))

    def test_get_assigned_roles(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'pending_roles': ['controller']},
                {'pending_roles': ['ceph-osd', 'compute']},
                {'roles': ['compute']},
                {'roles': ['cinder']},
            ]
        )

        self.env.create(
            nodes_kwargs=[
                {'pending_roles': ['controller']},
                {'pending_roles': ['controller']},
                {'pending_roles': ['ceph-osd', 'compute']},
                {'pending_roles': ['compute']},
                {'pending_roles': ['cinder']},
            ]
        )

        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['ceph-osd', 'compute']},
                {'roles': ['cinder']},
            ]
        )

        expected_roles = set(['controller', 'compute', 'cinder', 'ceph-osd'])
        for cluster in self.env.clusters:
            self.assertEqual(expected_roles,
                             objects.Cluster.get_assigned_roles(cluster))
