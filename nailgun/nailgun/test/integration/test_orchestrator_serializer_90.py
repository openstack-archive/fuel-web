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
from nailgun.db.sqlalchemy import models

from nailgun.orchestrator.deployment_graph import AstuteGraph
from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestDeploymentHASerializer80
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer


class TestSerializer90Mixin(object):
    env_version = "liberty-9.0"


class TestDeploymentAttributesSerialization90(
    TestSerializer90Mixin,
    BaseDeploymentSerializer
):

    def setUp(self):
        super(TestDeploymentAttributesSerialization90, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={
                'version': self.env_version,
                'operating_system': consts.RELEASE_OS.ubuntu},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan})
        self.cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        self.serializer = serializer_type(AstuteGraph(self.cluster_db))

    def test_attributes_cpu_pinning(self):
        meta = {'numa_topology': {
            'numa_nodes': [{'id': 1, 'cpus': [1, 2, 3, 4]},
                           {'id': 2, 'cpus': [5, 6, 7, 8]}]
        }}
        node = self.env.create_node(cluster_id=self.cluster_db.id,
                                    roles=['compute'],
                                    meta=meta)
        node.attributes.update({
            'cpu_pinning': {
                'nova': {'value': 2},
                'dpdk': {'value': 2},
            }
        })

        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)

        serialized_node=  serialized_for_astute[0]
        self.assertEqual(serialized_node['dpdk']['ovs_core_mask'], '0x2')
        self.assertEqual(serialized_node['dpdk']['ovs_pmd_core_mask'], '0x4')
        self.assertEqual(serialized_node['nova']['enable_cpu_pinning'], True)
        self.assertEqual(serialized_node['nova']['cpu_pinning'], [3, 4])


class TestDeploymentHASerializer90(
    TestSerializer90Mixin,
    TestDeploymentHASerializer80
):
    def test_glance_properties(self):
        self.check_no_murano_data()
