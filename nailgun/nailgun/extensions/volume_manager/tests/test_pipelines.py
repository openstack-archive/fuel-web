# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator.orchestrator_graph import AstuteGraph
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer
from nailgun.test.integration.test_orchestrator_serializer import \
    OrchestratorSerializerTestBase
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestSerializer80Mixin
from nailgun.test.integration.test_orchestrator_serializer_90 import \
    TestSerializer90Mixin
from nailgun.utils import reverse


class TestBlockDeviceDevicesSerialization80(BaseDeploymentSerializer):
    env_version = 'liberty-8.0'

    def test_block_device_disks(self):
        self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan})
        self.cluster_db = self.env.clusters[0]

        self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['cinder-block-device']
        )
        self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['controller']
        )
        serialized_for_astute = deployment_serializers.serialize(
            AstuteGraph(self.cluster_db),
            self.cluster_db,
            self.cluster_db.nodes)
        for node in serialized_for_astute:
            self.assertIn("node_volumes", node)
            for node_volume in node["node_volumes"]:
                if node_volume["id"] == "cinder-block-device":
                    self.assertEqual(node_volume["volumes"], [])
                else:
                    self.assertNotEqual(node_volume["volumes"], [])


class TestBlockDeviceDevicesSerialization90(
    TestSerializer90Mixin,
    TestBlockDeviceDevicesSerialization80
):
    pass


class TestDeploymentAttributesSerialization80(
    TestSerializer80Mixin,
    BaseDeploymentSerializer
):
    env_version = 'liberty-8.0'

    def test_disks_attrs(self):
        self.cluster = self.env.create(
            release_kwargs={
                'version': self.env_version,
                'operating_system': consts.RELEASE_OS.ubuntu},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan})
        self.cluster_db = self.env.clusters[0]

        disks = [
            {
                "model": "TOSHIBA MK1002TS",
                "name": "sda",
                "disk": "sda",
                "size": 1004886016
            },
        ]
        expected_node_volumes_hash = [
            {
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
            },
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
        serialized_for_astute = deployment_serializers.serialize(
            AstuteGraph(self.cluster_db),
            self.cluster_db,
            self.cluster_db.nodes)

        for node in serialized_for_astute:
            self.assertIn("node_volumes", node)
            self.assertItemsEqual(
                expected_node_volumes_hash, node["node_volumes"])


class TestCephPgNumOrchestratorSerialize(OrchestratorSerializerTestBase):

    env_version = '1111-6.0'

    def create_env(self, nodes, osd_pool_size='2'):
        cluster = self.env.create(
            release_kwargs={
                'version': self.env_version,
                'modes': [consts.CLUSTER_MODES.ha_compact,
                          consts.CLUSTER_MODES.multinode]},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.multinode},
            nodes_kwargs=nodes)
        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps(
                {'editable': {
                    'storage': {
                        'osd_pool_size': {'value': osd_pool_size}}}}),
            headers=self.default_headers)
        return self.env.clusters[0]

    @staticmethod
    def serialize(cluster):
        return deployment_serializers.serialize(
            AstuteGraph(cluster),
            cluster,
            cluster.nodes)

    def test_pg_num_no_osd_nodes(self):
        cluster = self.create_env([
            {'roles': ['controller']}])
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 128)

    def test_pg_num_1_osd_node(self):
        cluster = self.create_env([
            {'roles': ['controller', 'ceph-osd']}])
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 256)

    def test_pg_num_1_osd_node_repl_4(self):
        cluster = self.create_env(
            [{'roles': ['controller', 'ceph-osd']}],
            '4')
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 128)

    def test_pg_num_3_osd_nodes(self):
        cluster = self.create_env([
            {'roles': ['controller', 'ceph-osd']},
            {'roles': ['compute', 'ceph-osd']},
            {'roles': ['compute', 'ceph-osd']}])
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 512)
