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
from nailgun.test.base import BaseTestCase
from nailgun.test.base import fake_tasks


class TestCluster(BaseTestCase):

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
            api=True,
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

        # Checking no primary before deployment
        self.assertIsNone(objects.Cluster.get_primary_node(
            cluster, 'controller'))
        self.assertIsNone(objects.Cluster.get_primary_node(
            cluster, 'compute'))
        self.assertIsNone(objects.Cluster.get_primary_node(
            cluster, 'fake_role'))

        # Checking primary after deployment
        deploy = self.env.launch_deployment()
        self.env.wait_ready(deploy)
        self.assertIsNotNone(objects.Cluster.get_primary_node(
            cluster, 'controller'))
        self.assertIsNone(objects.Cluster.get_primary_node(
            cluster, 'compute'))
        self.assertIsNone(objects.Cluster.get_primary_node(
            cluster, 'fake_role'))

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
        self.env.wait_ready(deploy)

        primary_controller = objects.Cluster.get_primary_node(
            cluster, 'controller')
        self.assertIsNotNone(primary_controller)
        self.assertIsNone(objects.Cluster.get_primary_node(
            cluster, 'compute'))
        self.assertIsNone(objects.Cluster.get_primary_node(
            cluster, 'fake_role'))

        # Checking no primary for pending deleting nodes
        primary_controller.pending_deletion = True
        self.env.db().flush()

        self.assertIsNone(objects.Cluster.get_primary_node(
            cluster, 'controller'))
        self.assertIsNone(objects.Cluster.get_primary_node(
            cluster, 'compute'))
        self.assertIsNone(objects.Cluster.get_primary_node(
            cluster, 'fake_role'))
