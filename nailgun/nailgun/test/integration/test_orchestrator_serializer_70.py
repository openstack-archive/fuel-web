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

import mock

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.network.manager import NetworkManager
from nailgun import objects
from nailgun.orchestrator.deployment_graph import AstuteGraph
from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer


class TestDeploymentAttributesSerialization70(BaseDeploymentSerializer):
    @mock.patch('nailgun.utils.extract_env_version', return_value='7.0')
    def setUp(self, *args):
        super(TestDeploymentAttributesSerialization70, self).setUp()
        self.cluster = self.create_env('ha_compact')

        # NOTE: 'prepare_for_deployment' is going to be changed for 7.0
        objects.NodeCollection.prepare_for_deployment(self.env.nodes, 'vlan')
        cluster_db = self.db.query(Cluster).get(self.cluster['id'])
        serializer = get_serializer_for_cluster(cluster_db)
        self.serialized_for_astute = serializer(
            AstuteGraph(cluster_db)).serialize(cluster_db, cluster_db.nodes)

    def create_env(self, mode):
        return self.env.create(
            cluster_kwargs={
                'mode': mode,
                'net_provider': 'neutron',
                'net_segment_type': 'vlan'},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'pending_addition': True,
                 'name': self.node_name,
                 }
            ])

    def test_network_scheme(self):
        for node in self.serialized_for_astute:
            roles = node['network_scheme']['roles']
            expected_roles = {
                'admin/pxe': 'br-fw-admin',

                'keystone/api': 'br-mgmt',
                'neutron/api': 'br-mgmt',
                'swift/api': 'br-mgmt',
                'sahara/api': 'br-mgmt',
                'ceilometer/api': 'br-mgmt',
                'cinder/api': 'br-mgmt',
                'glance/api': 'br-mgmt',
                'heat/api': 'br-mgmt',
                'nova/api': 'br-mgmt',
                'murano/api': 'br-mgmt',
                'horizon': 'br-mgmt',

                'mgmt/api': 'br-mgmt',
                'mgmt/database': 'br-mgmt',
                'mgmt/messaging': 'br-mgmt',
                'mgmt/corosync': 'br-mgmt',
                'mgmt/vip': 'br-mgmt',

                'public/vip': 'br-ex',

                'neutron/private': 'br-prv',
                'neutron/mesh': 'br-mgmt',
                'neutron/floating': 'br-floating',

                'swift/public': 'br-ex',
                'swift/replication': 'br-storage',

                'ceph/public': 'br-mgmt',
                'ceph/radosgw': 'br-ex',
                'ceph/replication': 'br-storage',

                'cinder/iscsi': 'br-storage',

                'mongo/db': 'br-mgmt',

                # deprecated
                'fw-admin': 'br-fw-admin',
                'management': 'br-mgmt',
                'ex': 'br-ex',
                'storage': 'br-storage',
            }
            self.assertEqual(roles, expected_roles)

    def test_offloading_modes_serialize(self):
        meta = self.env.default_metadata()
        changed_offloading_modes = {}
        for interface in meta['interfaces']:
            changed_offloading_modes[interface['name']] = \
                NetworkManager._get_modified_offloading_modes(
                    interface.get('offloading_modes')
                )

        for node in self.serialized_for_astute:
            interfaces = node['network_scheme']['interfaces']
            for iface_name in interfaces:
                ethtool_blk = interfaces[iface_name].get('ethtool', None)
                self.assertIsNotNone(ethtool_blk)
                offload_blk = ethtool_blk.get('offload', None)
                self.assertIsNotNone(offload_blk)
                self.assertDictEqual(offload_blk,
                                     changed_offloading_modes[iface_name])
