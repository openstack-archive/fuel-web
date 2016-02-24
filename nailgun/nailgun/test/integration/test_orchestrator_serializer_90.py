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

from nailgun import consts
from nailgun import objects
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer90
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer90

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
    @mock.patch('nailgun.objects.Node.get_supported_dpdk_drivers')
    def test_serialization_with_dpdk(self, drivers_mock):
        drivers_mock.return_value = {
            'driver_1': ['test_id:1', 'test_id:2']
        }
        node = self.env.create_nodes_w_interfaces_count(
            1, 3,
            cluster_id=self.cluster_db.id,
            roles=['compute'])[0]

        nic_1 = node.interfaces[0]
        nic_2 = node.interfaces[2]
        nets_1 = nic_1.assigned_networks_list
        nets_2 = nic_2.assigned_networks_list

        dpdk_interface_name = nic_2.name

        for i, net in enumerate(nets_1):
            if net['name'] == 'private':
                nets_2.append(nets_1.pop(i))
                break
        objects.NIC.assign_networks(nic_1, nets_1)
        objects.NIC.assign_networks(nic_2, nets_2)

        objects.NIC.update(nic_2,
                           {'interface_properties':
                               {
                                   'dpdk': {'enabled': True,
                                            'available': True},
                                   'pci_id': 'test_id:2'
                               }})
        objects.Cluster.prepare_for_deployment(self.cluster_db)

        serialised_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        self.assertEqual(len(serialised_for_astute), 1)
        node = serialised_for_astute[0]
        dpdk = node.get('dpdk')
        self.assertIsNotNone(dpdk)
        self.assertTrue(dpdk.get('enabled'))

        transformations = node['network_scheme']['transformations']
        private_br = filter(lambda t: t.get('name') ==
                            consts.DEFAULT_BRIDGES_NAMES.br_prv,
                            transformations)[0]
        dpdk_port = filter(lambda t: t.get('bridge') ==
                           consts.DEFAULT_BRIDGES_NAMES.br_prv,
                           transformations)[0]
        self.assertEqual(private_br.get('vendor_specific'),
                         {'datapath_type': 'netdev'})
        self.assertEqual(dpdk_port.get('provider'), 'dpdkovs')

        interfaces = node['network_scheme']['interfaces']
        dpdk_interface = interfaces[dpdk_interface_name]
        vendor_specific = dpdk_interface.get('vendor_specific', {})
        self.assertEqual(vendor_specific.get('dpdk_driver'), 'driver_1')

    @mock.patch('nailgun.objects.Node.get_supported_dpdk_drivers')
    def test_serialization_with_dpdk_on_bond(self, drivers_mock):
        drivers_mock.return_value = {
            'driver_1': ['test_id:1', 'test_id:2']
        }
        node = self.env.create_nodes_w_interfaces_count(
            1, 4,
            cluster_id=self.cluster_db.id,
            roles=['compute'])[0]

        for iface in node.interfaces:
            iface['interface_properties'].update({'pci_id': 'test_id:1'})

        interfaces = self.env.node_nics_get(node.id).json_body

        first_nic = interfaces[0]
        nics_for_bond = [interfaces.pop(), interfaces.pop()]

        networks_for_bond = []
        bond_interface_name = 'bond0'

        first_nic_networks = first_nic['assigned_networks']
        for i, net in enumerate(first_nic_networks):
            if net['name'] == 'private':
                networks_for_bond.append(first_nic_networks.pop(i))
                break

        interfaces.append(
            {
                'name': bond_interface_name,
                'type': consts.NETWORK_INTERFACE_TYPES.bond,
                'mode': consts.BOND_MODES.balance_slb,
                'slaves': nics_for_bond,
                'assigned_networks': networks_for_bond,
                'interface_properties':
                    {
                        'dpdk': {'enabled': True}
                    }
            }
        )
        self.env.node_nics_put(node.id, interfaces)
        objects.Cluster.prepare_for_deployment(self.cluster_db)

        serialised_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        self.assertEqual(len(serialised_for_astute), 1)
        node = serialised_for_astute[0]
        dpdk = node.get('dpdk')
        self.assertIsNotNone(dpdk)
        self.assertTrue(dpdk.get('enabled'))

        transformations = node['network_scheme']['transformations']
        private_br = filter(lambda t: t.get('name') ==
                            consts.DEFAULT_BRIDGES_NAMES.br_prv,
                            transformations)[0]
        dpdk_port = filter(lambda t: t.get('bridge') ==
                           consts.DEFAULT_BRIDGES_NAMES.br_prv,
                           transformations)[0]
        self.assertEqual(private_br.get('vendor_specific'),
                         {'datapath_type': 'netdev'})
        self.assertEqual(dpdk_port.get('provider'), 'dpdkovs')

        interfaces = node['network_scheme']['interfaces']
        for iface in nics_for_bond:
            dpdk_interface = interfaces[iface['name']]
            vendor_specific = dpdk_interface.get('vendor_specific', {})
            self.assertEqual(vendor_specific.get('dpdk_driver'), 'driver_1')


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


class TestSerializeInterfaceDriversData90(
    TestSerializer90Mixin,
    TestSerializeInterfaceDriversData80
):
    pass
