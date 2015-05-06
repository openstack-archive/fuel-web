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

from nailgun import objects
from nailgun.test.base import BaseTestCase


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
