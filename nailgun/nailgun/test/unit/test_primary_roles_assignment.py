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

import abc
from contextlib import contextmanager

import six

from nailgun import consts
from nailgun import objects
from nailgun.test import base


@six.add_metaclass(abc.ABCMeta)
class BasePrimaryRolesAssignmentTestCase(base.BaseTestCase):

    # NOTE(prmtl): need to mark it as not a test or pytest will try to run
    # "test_*" from it
    __test__ = False

    @abc.abstractproperty
    def role_name(self):
        pass

    @abc.abstractproperty
    def primary_role_name(self):
        pass

    def test_primary_controllers_assigned_for_pendings_roles(self):
        cluster = self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.ha_compact},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'pending_roles': [self.role_name],
                 'status': consts.NODE_STATUSES.discover,
                 'pending_addition': True},
                {'pending_roles': [self.role_name],
                 'status': consts.NODE_STATUSES.discover,
                 'pending_addition': True}])
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
        nodes = sorted(cluster.nodes, key=lambda node: node.id)
        # with lowest uid is assigned as primary
        self.assertEqual(
            objects.Node.all_roles(nodes[0]), [self.primary_role_name])
        self.assertEqual(
            objects.Node.all_roles(nodes[1]), [self.role_name])

    def test_primary_controller_assigned_for_ready_node(self):
        cluster = self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.ha_compact},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'pending_roles': [self.role_name],
                 'status': consts.NODE_STATUSES.discover,
                 'pending_addition': True},
                {'roles': [self.role_name],
                 'status': consts.NODE_STATUSES.ready,
                 'pending_addition': True}])
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
        # primary assigned to node with ready status
        nodes = sorted(cluster.nodes, key=lambda node: node.id)
        ready_node = next(n for n in cluster.nodes
                          if n.status == consts.NODE_STATUSES.ready)
        self.assertEqual(nodes[1], ready_node)
        self.assertEqual(
            objects.Node.all_roles(nodes[1]), [self.primary_role_name])
        self.assertEqual(
            objects.Node.all_roles(nodes[0]), [self.role_name])

    def test_primary_assignment_multinode(self):
        """Primary should not be assigned in multinode env."""
        cluster = self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.multinode},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu',
                            'modes': [consts.CLUSTER_MODES.ha_compact,
                                      consts.CLUSTER_MODES.multinode]},
            nodes_kwargs=[
                {'pending_roles': [self.role_name],
                 'status': consts.NODE_STATUSES.discover,
                 'pending_addition': True},
                {'roles': [self.role_name],
                 'status': consts.NODE_STATUSES.ready,
                 'pending_addition': True}])
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
        self.assertEqual(
            objects.Node.all_roles(cluster.nodes[0]), [self.role_name])
        self.assertEqual(
            objects.Node.all_roles(cluster.nodes[1]), [self.role_name])

    def test_primary_not_assigned_to_pending_deletion(self):
        cluster = self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.ha_compact},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'roles': [self.role_name],
                 'status': consts.NODE_STATUSES.ready,
                 'pending_deletion': True}])
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
        self.assertEqual(
            objects.Node.all_roles(cluster.nodes[0]), [self.role_name])

    @contextmanager
    def assert_node_reassigned(self):
        cluster = self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.ha_compact},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'pending_roles': [self.role_name],
                 'status': consts.NODE_STATUSES.discover,
                 'pending_addition': True},
                {'roles': [self.role_name],
                 'status': consts.NODE_STATUSES.ready,
                 'pending_addition': True}])
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
        nodes = sorted(cluster.nodes, key=lambda node: node.id)
        self.assertEqual(
            objects.Node.all_roles(nodes[1]), [self.primary_role_name])
        self.assertEqual(
            objects.Node.all_roles(nodes[0]), [self.role_name])
        yield nodes[1]
        objects.Cluster.set_primary_roles(cluster, cluster.nodes)
        self.assertEqual(
            objects.Node.all_roles(nodes[0]), [self.primary_role_name])

    def test_primary_assign_after_reset_to_discovery(self):
        """Removing primary roles after resetting node to discovery"""
        with self.assert_node_reassigned() as node:
            objects.Node.reset_to_discover(node)

    def test_primary_assign_after_node_is_removed_from_cluster(self):
        """Node removal from cluster should cause flushing its primary roles"""
        with self.assert_node_reassigned() as node:
            objects.Node.remove_from_cluster(node)


class TestControllerPrimaryRolesAssignment(BasePrimaryRolesAssignmentTestCase):
    __test__ = True

    role_name = 'controller'
    primary_role_name = 'primary-controller'


class TestMongoPrimaryRolesAssignment(BasePrimaryRolesAssignmentTestCase):
    __test__ = True

    role_name = 'mongo'
    primary_role_name = 'primary-mongo'
