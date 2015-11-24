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
from nailgun.db.sqlalchemy import models
from nailgun import objects

from nailgun.orchestrator.deployment_graph import AstuteGraph
from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer80
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer80
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer
from nailgun.test.integration.test_orchestrator_serializer import \
    TestSerializeInterfaceDriversData
from nailgun.test.integration.test_orchestrator_serializer_70 import \
    TestDeploymentHASerializer70


class TestNetworkTemplateSerializer80(BaseDeploymentSerializer):
    env_version = '2015.1.0-8.0'
    prepare_for_deployment = objects.NodeCollection.prepare_for_deployment

    def setUp(self, *args):
        super(TestNetworkTemplateSerializer80, self).setUp()
        cluster = self.create_env(consts.CLUSTER_MODES.ha_compact)
        self.net_template = self.env.read_fixtures(['network_template'])[0]
        self.cluster = self.db.query(models.Cluster).get(cluster['id'])

    def test_get_net_provider_serializer(self):
        serializer = get_serializer_for_cluster(self.cluster)
        self.cluster.network_config.configuration_template = None

        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, NeutronNetworkDeploymentSerializer80)

        self.cluster.network_config.configuration_template = \
            self.net_template
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, NeutronNetworkTemplateSerializer80)


class TestSerializer80Mixin(object):
    env_version = "2015.1.0-8.0"

    def prepare_for_deployment(self, nodes, *_):
        objects.NodeCollection.prepare_for_deployment(nodes)


class TestDeploymentAttributesSerialization80(BaseDeploymentSerializer):
    env_version = '2015.1.0-8.0'

    def setUp(self):
        super(TestDeploymentAttributesSerialization80, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan})
        self.cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        self.serializer = serializer_type(AstuteGraph(self.cluster_db))

    def test_neutron_attrs(self):
        self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['controller'], primary_roles=['controller']
        )
        self.prepare_for_deployment(self.env.nodes)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        for node in serialized_for_astute:
            self.assertEqual(
                {
                    "bridge": consts.DEFAULT_BRIDGES_NAMES.br_floating,
                    "vlan_range": None
                },
                node['quantum_settings']['L2']['phys_nets']['physnet1']
            )

    def test_disks_attrs(self):
        disks = [
            {
                "model": "TOSHIBA MK1002TS",
                "name": "sda",
                "disk": "sda",
                "size": 1004886016
            },
        ]
        expected_disk_hash = [{
            u'name': u'sda',
            u'extra': [],
            u'free_space': 330,
            u'volumes': [
                {
                    u'type': u'boot',
                    u'size': 300
                },
                {
                    u'mount': u'/boot',
                    u'type': u'partition',
                    u'file_system': u'ext2',
                    u'name': u'Boot',
                    u'size': 200
                },
                {
                    u'type': u'lvm_meta_pool',
                    u'size': 64
                },
                {
                    u'vg': u'os',
                    u'type': u'pv',
                    u'lvm_meta_size': 64,
                    u'size': 394
                },
                {
                    u'vg': u'vm',
                    u'type': u'pv',
                    u'lvm_meta_size': 0,
                    u'size': 0
                }
            ],
            u'type': u'disk',
            u'id': u'sda',
            u'size': 958
        }]
        expected_volume_groups_hash = [
            {
                u'_allocate_size': u'min',
                u'label': u'Base System',
                u'min_size': 19456,
                u'volumes': [
                    {
                        u'mount': u'/',
                        u'size': -3766,
                        u'type': u'lv',
                        u'name': u'root',
                        u'file_system': u'ext4'
                    },
                    {
                        u'mount': u'swap',
                        u'size': 4096,
                        u'type': u'lv',
                        u'name': u'swap',
                        u'file_system': u'swap'
                    }
                ],
                u'type': u'vg',
                u'id': u'os'
            },
            {
                u'_allocate_size': u'all',
                u'label': u'Virtual Storage',
                u'min_size': 5120,
                u'volumes': [
                    {
                        u'mount': u'/var/lib/nova',
                        u'size': 0,
                        u'type': u'lv',
                        u'name': u'nova',
                        u'file_system': u'xfs'
                    }
                ],
                u'type': u'vg',
                u'id': u'vm'
            }
        ]
        self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['compute'],
            meta={"disks": disks},
        )
        self.prepare_for_deployment(self.env.nodes)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        for node in serialized_for_astute:
            self.assertIn("disks", node)
            self.assertEqual(expected_disk_hash, node["disks"])
            self.assertIn("volume_groups", node)
            self.assertEqual(expected_volume_groups_hash,
                             node["volume_groups"])


class TestSerializeInterfaceDriversData80(
    TestSerializer80Mixin,
    TestSerializeInterfaceDriversData
):
    pass


class TestDeploymentHASerializer80(
    TestSerializer80Mixin,
    TestDeploymentHASerializer70
):
    pass
