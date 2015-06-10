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
import six

from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun.network.manager import NetworkManager
from nailgun import objects
from nailgun.orchestrator.deployment_graph import AstuteGraph
from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer


class TestDeploymentAttributesSerialization70(BaseDeploymentSerializer):
    @mock.patch.object(models.Release, 'environment_version',
                       new_callable=mock.PropertyMock(return_value='7.0'))
    def setUp(self, *args):
        super(TestDeploymentAttributesSerialization70, self).setUp()
        self.cluster = self.create_env('ha_compact')

        # NOTE: 'prepare_for_deployment' is going to be changed for 7.0
        objects.NodeCollection.prepare_for_deployment(self.env.nodes, 'vlan')
        cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(cluster_db)
        self.serializer = serializer_type(AstuteGraph(cluster_db))
        self.serialized_for_astute = self.serializer.serialize(
            cluster_db, cluster_db.nodes)
        self.vm_data = self.env.read_fixtures(['vmware_attributes'])

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

    def test_provider_cluster_attrs(self):
        for node in self.serialized_for_astute:
            quantum_settings = node['quantum_settings']
            self.assertNotIn('L2', quantum_settings)
            self.assertNotIn('L3', quantum_settings)

            self.assertIsNot(quantum_settings['database']['passwd'], '')
            self.assertIsNot(quantum_settings['keystone']['admin_password'],
                             '')
            self.assertIsNot(
                quantum_settings['metadata']['metadata_proxy_shared_secret'],
                '')

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
                'mgmt/memcache': 'br-mgmt',
                'mgmt/vip': 'br-mgmt',

                'public/vip': 'br-ex',

                'neutron/mesh': 'br-mgmt',
                'neutron/floating': 'br-floating',
                'neutron/private': 'br-prv',
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
                self.assertIsNotNone(
                    ethtool_blk,
                    "There is no 'ethtool' block in deployment data")
                offload_blk = ethtool_blk.get('offload', None)
                self.assertIsNotNone(
                    offload_blk,
                    "There is no 'offload' block in deployment data")
                self.assertDictEqual(offload_blk,
                                     changed_offloading_modes[iface_name])

    def test_network_metadata(self):
        nm = objects.Cluster.get_network_manager(self.env.clusters[0])
        ip_by_net = {
            'fuelweb_admin': None,
            'storage': None,
            'management': None,
            'public': None
        }
        node = self.env.nodes[0]
        for net in ip_by_net:
            netgroup = nm.get_node_network_by_netname(node, net)
            if netgroup.get('ip'):
                ip_by_net[net] = netgroup['ip'].split('/')[0]
        for node_data in self.serialized_for_astute:
            self.assertItemsEqual(
                node_data['network_metadata'], ['nodes', 'vips'])
            for k, v in six.iteritems(node_data['network_metadata']['nodes']):
                self.assertItemsEqual(
                    v,
                    ['uid', 'fqdn', 'name', 'user_node_name',
                     'swift_zone', 'node_roles', 'network_roles']
                )
                self.assertEqual(objects.Node.make_slave_name(node), k)
                self.assertEqual(v['uid'], node.uid)
                self.assertEqual(v['fqdn'], node.fqdn)
                self.assertEqual(v['name'], k)
                self.assertEqual(v['user_node_name'], node.name)
                self.assertEqual(v['swift_zone'], node.uid)

                network_roles = {
                    'admin/pxe': ip_by_net['fuelweb_admin'],
                    'fw-admin': ip_by_net['fuelweb_admin'],

                    'keystone/api': ip_by_net['management'],
                    'neutron/api': ip_by_net['management'],
                    'swift/api': ip_by_net['management'],
                    'sahara/api': ip_by_net['management'],
                    'ceilometer/api': ip_by_net['management'],
                    'cinder/api': ip_by_net['management'],
                    'glance/api': ip_by_net['management'],
                    'heat/api': ip_by_net['management'],
                    'nova/api': ip_by_net['management'],
                    'murano/api': ip_by_net['management'],
                    'horizon': ip_by_net['management'],

                    'management': ip_by_net['management'],
                    'mgmt/api': ip_by_net['management'],
                    'mgmt/database': ip_by_net['management'],
                    'mgmt/messaging': ip_by_net['management'],
                    'mgmt/corosync': ip_by_net['management'],
                    'mgmt/memcache': ip_by_net['management'],
                    'mgmt/vip': ip_by_net['management'],

                    'mongo/db': ip_by_net['management'],

                    'neutron/mesh': ip_by_net['management'],

                    'ceph/public': ip_by_net['management'],

                    'neutron/private': None,
                    'neutron/floating': None,

                    'storage': ip_by_net['storage'],
                    'ceph/replication': ip_by_net['storage'],
                    'swift/replication': ip_by_net['storage'],
                    'cinder/iscsi': ip_by_net['storage'],

                    'ex': ip_by_net['public'],
                    'public/vip': ip_by_net['public'],
                    'ceph/radosgw': ip_by_net['public'],
                }
                self.assertEqual(
                    v['network_roles'],
                    network_roles
                )

    def test_generate_vmware_attributes_data(self):
        self.check_generate_vmware_attributes_data()


class TestDeploymentSerializationForNovaNetwork70(BaseDeploymentSerializer):
    @mock.patch.object(models.Release, 'environment_version',
                       new_callable=mock.PropertyMock(return_value='7.0'))
    def setUp(self, *args):
        super(TestDeploymentSerializationForNovaNetwork70, self).setUp()
        self.cluster = self.create_env('ha_compact')

        # NOTE: 'prepare_for_deployment' is going to be changed for 7.0
        objects.NodeCollection.prepare_for_deployment(self.env.nodes)
        cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(cluster_db)
        self.serializer = serializer_type(AstuteGraph(cluster_db))
        self.serialized_for_astute = self.serializer.serialize(
            cluster_db, cluster_db.nodes)
        self.vm_data = self.env.read_fixtures(['vmware_attributes'])

    def create_env(self, mode):
        return self.env.create(
            cluster_kwargs={
                'mode': mode,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network},
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
                'mgmt/memcache': 'br-mgmt',
                'mgmt/vip': 'br-mgmt',

                'public/vip': 'br-ex',

                'swift/replication': 'br-storage',

                'ceph/public': 'br-mgmt',
                'ceph/radosgw': 'br-ex',
                'ceph/replication': 'br-storage',

                'cinder/iscsi': 'br-storage',

                'mongo/db': 'br-mgmt',

                'novanetwork/fixed': 'eth0.103',

                # deprecated
                'fw-admin': 'br-fw-admin',
                'management': 'br-mgmt',
                'ex': 'br-ex',
                'storage': 'br-storage',
            }
            self.assertEqual(roles, expected_roles)

    def test_network_metadata(self):
        nm = objects.Cluster.get_network_manager(self.env.clusters[0])
        ip_by_net = {
            'fuelweb_admin': None,
            'storage': None,
            'management': None,
            'public': None
        }
        node = self.env.nodes[0]
        for net in ip_by_net:
            netgroup = nm.get_node_network_by_netname(node, net)
            if netgroup.get('ip'):
                ip_by_net[net] = netgroup['ip'].split('/')[0]
        for node_data in self.serialized_for_astute:
            self.assertItemsEqual(
                node_data['network_metadata'], ['nodes', 'vips'])
            for k, v in six.iteritems(node_data['network_metadata']['nodes']):
                self.assertItemsEqual(
                    v,
                    ['uid', 'fqdn', 'name', 'user_node_name',
                     'swift_zone', 'node_roles', 'network_roles']
                )
                self.assertEqual(objects.Node.make_slave_name(node), k)
                self.assertEqual(v['uid'], node.uid)
                self.assertEqual(v['fqdn'], node.fqdn)
                self.assertEqual(v['name'], k)
                self.assertEqual(v['user_node_name'], node.name)
                self.assertEqual(v['swift_zone'], node.uid)

                network_roles = {
                    'admin/pxe': ip_by_net['fuelweb_admin'],
                    'fw-admin': ip_by_net['fuelweb_admin'],

                    'keystone/api': ip_by_net['management'],
                    'swift/api': ip_by_net['management'],
                    'sahara/api': ip_by_net['management'],
                    'ceilometer/api': ip_by_net['management'],
                    'cinder/api': ip_by_net['management'],
                    'glance/api': ip_by_net['management'],
                    'heat/api': ip_by_net['management'],
                    'nova/api': ip_by_net['management'],
                    'murano/api': ip_by_net['management'],
                    'horizon': ip_by_net['management'],

                    'management': ip_by_net['management'],
                    'mgmt/api': ip_by_net['management'],
                    'mgmt/database': ip_by_net['management'],
                    'mgmt/messaging': ip_by_net['management'],
                    'mgmt/corosync': ip_by_net['management'],
                    'mgmt/memcache': ip_by_net['management'],
                    'mgmt/vip': ip_by_net['management'],

                    'mongo/db': ip_by_net['management'],

                    'ceph/public': ip_by_net['management'],

                    'storage': ip_by_net['storage'],
                    'ceph/replication': ip_by_net['storage'],
                    'swift/replication': ip_by_net['storage'],
                    'cinder/iscsi': ip_by_net['storage'],

                    'ex': ip_by_net['public'],
                    'public/vip': ip_by_net['public'],
                    'ceph/radosgw': ip_by_net['public'],
                }
                self.assertEqual(
                    v['network_roles'],
                    network_roles
                )

    def test_generate_vmware_attributes_data(self):
        self.check_generate_vmware_attributes_data()

    def test_network_metadata(self):
        for node in self.serialized_for_astute:
            roles = node['network_metadata']['roles']

            # 'neutron/private' role test
            neutron_private_expected = {
                "tenant_networks": {
                    "enabled": True,
                    "type": "vlan",
                    "segm_range": [1000, 1030],
                    "networks": [
                        {
                            "name": "admin__vlan",
                            "segm_id": 1000,
                            "subnet": '192.168.111.0/24',
                            "gateway": '192.168.111.1',
                            "tenant_name": "admin",
                            "mtu": 0
                        }
                    ]
                }
            }
            self.assertEqual(roles['neutron/private'],
                             neutron_private_expected)

            # 'neutron/mesh' role test
            neutron_mesh_expected = {
                "tenant_networks": {
                    "enabled": True,
                    "type": "vxlan",
                    "segm_range": [
                        10000,
                        65535
                    ],
                    "networks": [
                        {
                            "name": "admin__vxlan",
                            "segm_id": 10000,
                            "subnet": "192.128.112.0/24",
                            "gateway": "192.128.112.1",
                            "tenant_name": "admin",
                            "mtu": 0
                        }
                    ]
                }
            }
            self.assertEqual(roles['neutron/mesh'], neutron_mesh_expected)

            # 'neutron/floating' role test
            neutron_floating_expected = {
                "floating_subnets": [
                    {
                        "name": "floating__sub_1",
                        "subnet": '172.16.0.0/24',
                        "range": {
                            "start": '172.16.0.130',
                            "end": '172.16.0.254'
                        },
                        "gw": '172.16.0.1'
                    },
                ]
            }
            self.assertEqual(roles['neutron/floating'],
                             neutron_floating_expected)

            # 'neutron/api' role test
            neutron_api_expected = {
                "tenant_networks": [
                    {
                        "base_mac": "fa:16:3e:00:00:00",
                        "l2_population": False,
                        "use_dvr": False,
                        "nameservers": ['8.8.4.4', '8.8.8.8']
                    },
                ]
            }
            self.assertEqual(roles['neutron/api'],
                             neutron_api_expected)
