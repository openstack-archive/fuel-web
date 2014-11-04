# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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


from nailgun.task import helpers
from nailgun.test import base


class TestClusterRedeploymentScenario(base.BaseTestCase):

    def test_cluster_deployed_with_computes(self):
        self.env.create(
            cluster_kwargs={'mode': 'multinode'},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'status': 'discover',
                 'pending_addition': True},
                {'roles': ['compute'],
                 'status': 'ready'}])
        cluster = self.env.clusters[0]
        nodes = helpers.TaskHelper.nodes_to_deploy(cluster)
        self.assertEqual(cluster.nodes, nodes)

    def test_cluster_deployed_with_cinder(self):
        self.env.create(
            cluster_kwargs={'mode': 'multinode'},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'status': 'discover',
                 'pending_addition': True},
                {'roles': ['cinder'],
                 'status': 'ready'}])
        cluster = self.env.clusters[0]
        nodes = helpers.TaskHelper.nodes_to_deploy(cluster)
        self.assertEqual(cluster.nodes, nodes)

    def test_ceph_osd_is_not_affected(self):
        self.env.create(
            cluster_kwargs={'mode': 'multinode'},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'pending_roles': ['controller'],
                 'status': 'discover',
                 'pending_addition': True},
                {'roles': ['ceph-osd'],
                 'status': 'ready'}])
        cluster = self.env.clusters[0]
        nodes = helpers.TaskHelper.nodes_to_deploy(cluster)
        self.assertNotEqual(cluster.nodes, nodes)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].pending_roles, ['controller'])

    def test_cinder_is_not_affected_when_add_compute(self):
        self.env.create(
            cluster_kwargs={'mode': 'multinode'},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'status': 'ready'},
                {'pending_roles': ['compute'],
                 'status': 'discover',
                 'pending_addition': True},
                {'roles': ['cinder'],
                 'status': 'ready'}])
        cluster = self.env.clusters[0]
        nodes = helpers.TaskHelper.nodes_to_deploy(cluster)
        self.assertNotEqual(cluster.nodes, nodes)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].pending_roles, ['compute'])

    def test_controllers_redeployed_if_ceph_added(self):
        self.env.create(
            cluster_kwargs={'mode': 'multinode'},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'status': 'ready'},
                {'pending_roles': ['ceph-osd'],
                 'status': 'discover',
                 'pending_addition': True}])
        cluster = self.env.clusters[0]
        nodes = helpers.TaskHelper.nodes_to_deploy(cluster)
        self.assertEqual(len(nodes), 2)
        self.assertEqual(sorted(cluster.nodes), sorted(nodes))

    def test_controllers_not_redeployed_if_ceph_previously_in_cluster(self):
        self.env.create(
            cluster_kwargs={'mode': 'multinode'},
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'status': 'ready'},
                {'roles': ['ceph-osd'],
                 'status': 'ready'},
                {'pending_roles': ['ceph-osd'],
                 'status': 'discover',
                 'pending_addition': True}])
        cluster = self.env.clusters[0]
        nodes = helpers.TaskHelper.nodes_to_deploy(cluster)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].pending_roles, ['ceph-osd'])
