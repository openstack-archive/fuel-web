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

from nailgun.consts import NODE_STATUSES
from nailgun import objects
from nailgun.test import base


class TestPrimaryRolesAssignment(base.BaseTestCase):

    def test_primary_controllers_assigned_for_pendings_roles(self):
        self.env.create(
            cluster_kwargs={'mode': 'multinode'},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'status': 'discover',
                 'pending_addition': True},
                {'pending_roles': ['controller'],
                 'status': 'discover',
                 'pending_addition': True}])
        cluster = self.env.clusters[0]
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
        nodes = sorted(cluster.nodes, key=lambda node: node.id)
        # with lowest uid is assigned as primary
        self.assertEqual(
            objects.Node.all_roles(nodes[0]), ['primary-controller'])
        self.assertEqual(
            objects.Node.all_roles(nodes[1]), ['controller'])

    def test_primary_controller_assigned_for_ready_node(self):
        self.env.create(
            cluster_kwargs={'mode': 'multinode'},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'status': 'discover',
                 'pending_addition': True},
                {'roles': ['controller'],
                 'status': 'ready',
                 'pending_addition': True}])
        cluster = self.env.clusters[0]
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
        # primary assigned to node with ready status
        nodes = sorted(cluster.nodes, key=lambda node: node.id)
        ready_node = next(n for n in cluster.nodes
                          if n.status == NODE_STATUSES.ready)
        self.assertEqual(nodes[1], ready_node)
        self.assertEqual(
            objects.Node.all_roles(nodes[1]), ['primary-controller'])
        self.assertEqual(
            objects.Node.all_roles(nodes[0]), ['controller'])
