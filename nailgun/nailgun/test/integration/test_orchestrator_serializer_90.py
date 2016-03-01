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
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import deployment_serializers

from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer90
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer90

from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestBlockDeviceDevicesSerialization80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestDeploymentAttributesSerialization80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestDeploymentHASerializer80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestDeploymentTasksSerialization80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestMultiNodeGroupsSerialization80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestNetworkTemplateSerializer80
from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestSerializeInterfaceDriversData80


class TestSerializer90Mixin(object):
    env_version = "liberty-9.0"


class TestBlockDeviceDevicesSerialization90(
    TestSerializer90Mixin,
    TestBlockDeviceDevicesSerialization80
):
    pass


class TestDeploymentAttributesSerialization90(
    TestSerializer90Mixin,
    TestDeploymentAttributesSerialization80
):
    def test_attributes_cpu_pinning(self):
        numa_nodes = [{'id': 1, 'cpus': [1, 2, 3, 4]},
                      {'id': 2, 'cpus': [5, 6, 7, 8]}]
        node = self.env.create_node(cluster_id=self.cluster_db.id,
                                    roles=['compute'])

        node.meta['numa_topology']['numa_nodes'] = numa_nodes
        node.attributes.update({
            'cpu_pinning': {
                'nova': {'value': 2},
                'dpdk': {'value': 2},
            }
        })
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)

        serialized_node = serialized_for_astute[0]

        self.assertEqual(serialized_node['dpdk']['ovs_core_mask'], '0x2')
        self.assertEqual(serialized_node['dpdk']['ovs_pmd_core_mask'], '0x4')
        self.assertEqual(serialized_node['nova']['cpu_pinning'], [3, 4])
        node_name = objects.Node.get_slave_name(node)
        node_common_attrs = \
            serialized_node['network_metadata']['nodes'][node_name]
        self.assertTrue(node_common_attrs['nova_cpu_pinning_enabled'])

    def test_dpdk_hugepages(self):
        meta = {
            'numa_topology': {
                'supported_hugepages': [2048],
                'numa_nodes': [{'id': 0}, {'id': 1}, {'id': 2}]}
        }
        node = self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['compute'],
            meta=meta)
        node.attributes.update({
            'hugepages': {
                'dpdk': {
                    'value': 128},
                'nova': {
                    'value': {'2048': 1}}}}
        )

        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)

        serialized_node = serialized_for_astute[0]

        self.assertEquals(
            "128,128,128",
            serialized_node['dpdk']['ovs_socket_mem'])
        self.assertTrue(serialized_node['nova']['enable_hugepages'])


class TestDeploymentHASerializer90(
    TestSerializer90Mixin,
    TestDeploymentHASerializer80
):
    def test_glance_properties(self):
        self.check_no_murano_data()


class TestDeploymentTasksSerialization90(
    TestSerializer90Mixin,
    TestDeploymentTasksSerialization80
):
    pass


class TestMultiNodeGroupsSerialization90(
    TestSerializer90Mixin,
    TestMultiNodeGroupsSerialization80
):
    pass


class TestNetworkTemplateSerializer90(
    TestSerializer90Mixin,
    TestNetworkTemplateSerializer80
):
    legacy_serializer = NeutronNetworkDeploymentSerializer90
    template_serializer = NeutronNetworkTemplateSerializer90

    def check_selective_gateway(self, use_net_template=False):
        node = self.env.create_node(
            cluster_id=self.cluster.id,
            roles=['controller'], primary_roles=['controller']
        )
        objects.Cluster.set_network_template(
            self.cluster,
            self.net_template if use_net_template else None)
        objects.Cluster.prepare_for_deployment(self.cluster)

        serializer = deployment_serializers.get_serializer_for_cluster(
            self.cluster)
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        nm = objects.Cluster.get_network_manager(self.cluster)
        networks_list = nm.get_node_networks(node)
        networks = {net['name']: net for net in networks_list}
        endpoints = net_serializer.generate_network_scheme(
            node, networks_list)['endpoints']

        na = self.net_template[
            'adv_net_template']['default']['network_assignments']
        ep_net_map = {na[net_name]['ep']: net_name for net_name in na}

        for name in endpoints:
            if name not in ep_net_map:
                self.assertNotIn('vendor_specific', endpoints[name])
                continue
            if networks[ep_net_map[name]].get('gateway') is None:
                self.assertNotIn('vendor_specific', endpoints[name])
            else:
                self.assertIn('vendor_specific', endpoints[name])
                self.assertEqual(
                    endpoints[name]['vendor_specific']['provider_gateway'],
                    networks[ep_net_map[name]]['gateway'])

    def test_selective_gateway_in_deployment_serializer(self):
        self.check_selective_gateway()

    def test_selective_gateway_in_template_serializer(self):
        self.check_selective_gateway(use_net_template=True)


class TestSerializeInterfaceDriversData90(
    TestSerializer90Mixin,
    TestSerializeInterfaceDriversData80
):
    pass


class TestSriovSerialization90(
    TestSerializer90Mixin,
    BaseDeploymentSerializer
):
    def setUp(self, *args):
        super(TestSriovSerialization90, self).setUp()
        self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan,
                'status': consts.CLUSTER_STATUSES.new},
        )
        self.env.create_nodes_w_interfaces_count(
            nodes_count=1, if_count=3, cluster_id=self.env.clusters[0].id,
            pending_roles=['compute'], pending_addition=True)

    def serialize(self):
        objects.Cluster.prepare_for_deployment(self.env.clusters[0])
        graph = deployment_graph.AstuteGraph(self.env.clusters[0])
        return deployment_serializers.serialize(
            graph, self.env.clusters[0], self.env.nodes)

    def test_nic_sriov_info_is_serialized(self):
        for nic in self.env.nodes[0].nic_interfaces:
            if not nic.assigned_networks_list:
                nic_sriov = nic
                nic.interface_properties['sriov'] = {
                    'enabled': True,
                    'sriov_numvfs': 8,
                    'sriov_totalvfs': 8,
                    'available': True,
                    'pci_id': '1234:5678',
                    'physnet': 'new_physnet'
                }
                objects.NIC.update(
                    nic, {'interface_properties': nic.interface_properties})
                break
        else:
            self.fail('NIC without assigned networks was not found')

        node0 = self.serialize()[0]
        self.assertEqual(
            node0['quantum_settings']['supported_pci_vendor_devs'],
            ['1234:5678']
        )
        for trans in node0['network_scheme']['transformations']:
            if trans.get('name') == nic_sriov.name:
                self.assertEqual(
                    trans['vendor_specific'],
                    {
                        'sriov_numvfs': 8,
                        'physnet': 'new_physnet'
                    }
                )
                self.assertEqual(trans['provider'], 'sriov')
                break
        else:
            self.fail('NIC with SR-IOV enabled was not found')
