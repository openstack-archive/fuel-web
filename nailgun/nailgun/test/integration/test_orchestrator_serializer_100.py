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

from nailgun import consts
from nailgun import objects

from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator.deployment_serializers import \
    deployment_info_to_legacy
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer
from nailgun.test.integration import test_orchestrator_serializer_90


from nailgun.extensions.network_manager.serializers.neutron_serializers \
    import NeutronNetworkDeploymentSerializer100
from nailgun.extensions.network_manager.serializers.neutron_serializers \
    import NeutronNetworkTemplateSerializer100


class TestSerializer100Mixin(object):
    env_version = 'newton-10.0'
    task_deploy = True

    @classmethod
    def create_serializer(cls, cluster):
        return deployment_serializers.DeploymentLCMSerializer100()

    @classmethod
    def _get_serializer(cluster):
        return deployment_serializers.DeploymentLCMSerializer100()

    @staticmethod
    def _get_plugins_names(plugins):
        """Plugins names for LCM serializers

        Single out <name> since plugin data may contain
        <scripts>, <repositories>, <whatever> as well.

        :param nodes: array of plugins data
        :returns: singled out names of plugins
        """
        return [plugin['name'] for plugin in plugins]

    def _setup_cluster_with_ironic(self, ironic_provision_network,
                                   separate_interface=False):
        self.env._set_additional_component(self.cluster, 'ironic', True)
        if ironic_provision_network:
            objects.Cluster.patch_attributes(
                self.cluster,
                {'editable': {
                    'ironic_settings': {
                        'ironic_provision_network': {
                            'value': True}}}})
        node = self.env.create_nodes_w_interfaces_count(
            1, 4, cluster_id=self.cluster.id,
            roles=['controller', 'ironic'])[0]

        if separate_interface:
            nic_1 = node.nic_interfaces[0]
            nic_4 = node.nic_interfaces[3]
            nets_1 = nic_1.assigned_networks_list
            nets_4 = nic_4.assigned_networks_list
            for i, net in enumerate(nets_1):
                if net['name'] == 'baremetal':
                    nets_4.append(nets_1.pop(i))
                    break
            objects.NIC.assign_networks(nic_1, nets_1)
            objects.NIC.assign_networks(nic_4, nets_4)
        objects.Cluster.prepare_for_deployment(self.cluster)


class TestSerializeInterfaceDriversData100(
    TestSerializer100Mixin,
    test_orchestrator_serializer_90.TestSerializeInterfaceDriversData90
):
    pass


class TestDeploymentTasksSerialization100(
    TestSerializer100Mixin,
    test_orchestrator_serializer_90.TestDeploymentTasksSerialization90
):
    pass


class TestNetworkTemplateSerializer100(
    TestSerializer100Mixin,
    test_orchestrator_serializer_90.TestNetworkTemplateSerializer90
):
    pass


class TestNetworkDeploymentSerializer100(
    TestSerializer100Mixin,
    BaseDeploymentSerializer,
):

    legacy_serializer = NeutronNetworkDeploymentSerializer100
    template_serializer = NeutronNetworkTemplateSerializer100

    def setUp(self, *args):
        super(TestNetworkDeploymentSerializer100, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan})
        self.serializer = self.create_serializer(self.cluster)

    def test_baremetal_neutron_attrs_flat(self):
        self._setup_cluster_with_ironic(ironic_provision_network=False)
        serialized_for_astute = self.serializer.serialize(
            self.cluster, self.cluster.nodes)
        serialized_for_astute = deployment_info_to_legacy(
            serialized_for_astute)
        for node in serialized_for_astute:
            expected_network = {
                "network_type": "flat",
                "segment_id": None,
                "router_ext": False,
                "physnet": "physnet-ironic"
            }
            self.assertEqual(expected_network, node['quantum_settings']
                             ['predefined_networks']['baremetal']['L2'])
            self.assertIn("physnet-ironic",
                          node['quantum_settings']['L2']['phys_nets'])
            self.assertEqual(consts.DEFAULT_BRIDGES_NAMES.br_ironic,
                             (node['quantum_settings']['L2']['phys_nets']
                              ["physnet-ironic"]["bridge"]))
            self.assertEqual(None, (node['quantum_settings']['L2']['phys_nets']
                                    ["physnet-ironic"]["vlan_range"]))

    def test_baremetal_neutron_attrs_vlan(self):
        self._setup_cluster_with_ironic(ironic_provision_network=True)
        serialized_for_astute = self.serializer.serialize(
            self.cluster, self.cluster.nodes)
        serialized_for_astute = deployment_info_to_legacy(
            serialized_for_astute)
        for node in serialized_for_astute:
            expected_network = {
                "network_type": "vlan",
                "segment_id": 104,
                "router_ext": False,
                "physnet": "physnet-ironic"
            }
            self.assertEqual(expected_network, node['quantum_settings']
                             ['predefined_networks']['baremetal']['L2'])
            self.assertIn("physnet-ironic",
                          node['quantum_settings']['L2']['phys_nets'])
            self.assertEqual(consts.DEFAULT_BRIDGES_NAMES.br_ironic,
                             (node['quantum_settings']['L2']['phys_nets']
                              ["physnet-ironic"]["bridge"]))
            self.assertEqual('104:104',
                             (node['quantum_settings']['L2']['phys_nets']
                              ["physnet-ironic"]["vlan_range"]))

    def test_baremetal_transformations_flat(self):
        self._setup_cluster_with_ironic(ironic_provision_network=False)
        serialized_for_astute = self.serializer.serialize(
            self.cluster, self.cluster.nodes)
        serialized_for_astute = deployment_info_to_legacy(
            serialized_for_astute)
        net_tr = serialized_for_astute[0]['network_scheme']['transformations']
        expected_actions = [
            {'action': 'add-br', 'name': 'br-baremetal'},
            {'action': 'add-port', 'bridge': 'br-baremetal',
             'name': 'eth0.104'},
            {'action': 'add-br', 'name': 'br-ironic', 'provider': 'ovs'},
            {'action': 'add-patch', 'bridges': ['br-ironic', 'br-baremetal'],
             'provider': 'ovs'}]

        for element in expected_actions:
            self.assertIn(element, net_tr)

    def test_baremetal_transformations_vlan(self):
        self._setup_cluster_with_ironic(ironic_provision_network=True)
        serialized_for_astute = self.serializer.serialize(
            self.cluster, self.cluster.nodes)
        serialized_for_astute = deployment_info_to_legacy(
            serialized_for_astute)
        net_tr = serialized_for_astute[0]['network_scheme']['transformations']
        expected_actions = [
            {'action': 'add-br', 'name': 'br-bm-phy'},
            {'action': 'add-br', 'name': 'br-baremetal'},
            {'action': 'add-port', 'bridge': 'br-baremetal',
             'name': 'br-bm-phy.104'},
            {'action': 'add-br', 'name': 'br-ironic', 'provider': 'ovs'},
            {'action': 'add-patch', 'bridges': ['br-ironic', 'br-bm-phy'],
             'provider': 'ovs'},
            {'action': 'add-patch', 'bridges': ['br-bm-phy', 'br-fw-admin']}]

        not_expected = [
            {'action': 'add-port', 'bridge': 'br-bm-phy', 'name': u'eth0'}]

        for element in expected_actions:
            self.assertIn(element, net_tr)
        for elemnet in not_expected:
            self.assertNotIn(elemnet, net_tr)

    def test_baremetal_transformations_vlan_baremetal_on_separate_nic(self):
        self._setup_cluster_with_ironic(ironic_provision_network=True,
                                        separate_interface=True)
        serialized_for_astute = self.serializer.serialize(
            self.cluster, self.cluster.nodes)
        serialized_for_astute = deployment_info_to_legacy(
            serialized_for_astute)
        net_tr = serialized_for_astute[0]['network_scheme']['transformations']
        expected_actions = [
            {'action': 'add-br', 'name': 'br-bm-phy'},
            {'action': 'add-br', 'name': 'br-baremetal'},
            {'action': 'add-port', 'bridge': 'br-baremetal',
             'name': 'br-bm-phy.104'},
            {'action': 'add-br', 'name': 'br-ironic', 'provider': 'ovs'},
            {'action': 'add-patch', 'bridges': ['br-ironic', 'br-bm-phy'],
             'provider': 'ovs'},
            {'action': 'add-port', 'bridge': 'br-bm-phy', 'name': u'eth3'}]

        not_expected = [
            {'action': 'add-patch', 'bridges': ['br-bm-phy', 'br-fw-admin']}]

        for element in expected_actions:
            self.assertIn(element, net_tr)
        for elemnet in not_expected:
            self.assertNotIn(elemnet, net_tr)
