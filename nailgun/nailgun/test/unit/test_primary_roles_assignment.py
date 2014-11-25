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

from contextlib import contextmanager

from nailgun.consts import NODE_STATUSES
from nailgun import objects
from nailgun.test import base


class TestPrimaryRolesAssignment(base.BaseTestCase):

    def test_primary_controllers_assigned_for_pendings_roles(self):
        self.env.create(
            cluster_kwargs={'mode': 'ha_compact'},
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
            cluster_kwargs={'mode': 'ha_compact'},
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

    def test_primary_assignment_multinode(self):
        """Primary should not be assigned in multinode env."""
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
        self.assertEqual(
            objects.Node.all_roles(cluster.nodes[0]), ['controller'])
        self.assertEqual(
            objects.Node.all_roles(cluster.nodes[1]), ['controller'])

    def test_primary_not_assigned_to_pending_deletion(self):
        self.env.create(
            cluster_kwargs={'mode': 'ha_compact'},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'status': 'ready',
                 'pending_deletion': True}])
        cluster = self.env.clusters[0]
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
        self.assertEqual(
            objects.Node.all_roles(cluster.nodes[0]), ['controller'])

    @contextmanager
    def assert_node_reassigned(self):
        self.env.create(
            cluster_kwargs={'mode': 'ha_compact'},
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
        nodes = sorted(cluster.nodes, key=lambda node: node.id)
        self.assertEqual(
            objects.Node.all_roles(nodes[1]), ['primary-controller'])
        self.assertEqual(
            objects.Node.all_roles(nodes[0]), ['controller'])
        yield nodes[1]
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
        self.assertEqual(
            objects.Node.all_roles(nodes[0]), ['primary-controller'])

    def test_primary_assign_after_reset_to_discovery(self):
        """After node is reset to discovery, it will be booted into
        bootstrap once again, therefore we want to remove any primary
        roles assigned to this test
        """
        with self.assert_node_reassigned() as node:
            objects.Node.reset_to_discover(node)

    def test_primary_assign_after_node_is_removed_from_cluster(self):
        """When node is remove from cluster all primary roles
        assigned to this node should be flushed
        """
        with self.assert_node_reassigned() as node:
            objects.Node.remove_from_cluster(node)
