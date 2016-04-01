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

from nailgun.api.v1.validators.network import NetAssignmentValidator
from nailgun import consts
from nailgun.errors import errors
from nailgun import objects
from nailgun.test.base import BaseValidatorTest
from nailgun import utils


class BaseNetAssignmentValidatorTest(BaseValidatorTest):

    validator = NetAssignmentValidator.verify_data_correctness


class TestNetAssignmentValidator(BaseNetAssignmentValidatorTest):

    def test_verify_data_correctness_when_node_in_cluster(self):
        self.env.create(
            nodes_kwargs=[{
                'roles': ['controller'],
                'api': True}])
        node_data = self.env.nodes[0]
        self.validator(node_data)

    def test_verify_data_correctness_when_node_not_in_cluster(self):
        self.env.create_node()
        node_data = self.env.nodes[0]
        self.validator(node_data)


class TestDPDKValidation(BaseNetAssignmentValidatorTest):
    def setUp(self):
        super(TestDPDKValidation, self).setUp()
        self.patcher = mock.patch(
            'nailgun.objects.Release.get_supported_dpdk_drivers',
            return_value={'driver_1': ['test_id:1', 'test_id:2']}
        )
        self.patcher.start()

        cluster = self.env.create(
            api=False,
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan,
            }
        )

        self.cluster_db = self.env.clusters[-1]
        node = self.env.create_nodes_w_interfaces_count(
            1, 3, roles=['compute'], cluster_id=cluster['id'])[0]

        nic_1 = node.nic_interfaces[0]
        nic_2 = node.nic_interfaces[1]
        nic_3 = node.nic_interfaces[2]
        nets_1 = nic_1.assigned_networks_list
        nets_2 = nic_2.assigned_networks_list

        nets_1.extend(nets_2)
        nets_2 = nic_2.assigned_networks_list = []

        for i, net in enumerate(nets_1):
            if net['name'] == 'private':
                nets_2.append(nets_1.pop(i))
                break

        objects.NIC.assign_networks(nic_1, nets_1)
        objects.NIC.assign_networks(nic_2, nets_2)
        objects.NIC.assign_networks(nic_3, [])

        dpdk_settings = {
            'dpdk': {'enabled': True,
                     'available': True},
            'pci_id': 'test_id:2',
        }
        objects.NIC.update(nic_2, {'interface_properties': utils.dict_merge(
            nic_2.interface_properties, dpdk_settings)})

        dpdk_settings['dpdk']['enabled'] = False
        objects.NIC.update(nic_3, {'interface_properties': utils.dict_merge(
            nic_3.interface_properties, dpdk_settings)})

        node.attributes['hugepages'] = {
            'nova': {'type': 'custom_hugepages', 'value': {'2048': 1}},
            'dpdk': {'type': 'text', 'value': '1025'},
        }
        self.cluster_attrs = objects.Cluster.get_editable_attributes(
            self.cluster_db)

        self.cluster_attrs['common']['libvirt_type']['value'] = 'kvm'
        objects.Cluster.update_attributes(
            self.cluster_db, {'editable': self.cluster_attrs})

        self.node = node

        self.data = {'id': node.id,
                     'interfaces': self.env.node_nics_get(node.id).json_body}

    def tearDown(self):
        super(TestDPDKValidation, self).tearDown()
        self.patcher.stop()

    def check_fail(self, msg, data=None):
        if data is None:
            data = self.data

        self.assertRaisesRegexp(errors.InvalidData,
                                msg,
                                self.validator, data)

    def test_valid_dpdk_configuration(self):
        self.validator(self.node)

    def test_invalid_hypervisor(self):
        self.cluster_attrs['common']['libvirt_type']['value'] = 'quemu'
        objects.Cluster.update_attributes(
            self.cluster_db, {'editable': self.cluster_attrs})

        self.check_fail('Only KVM hypervisor works with DPDK')

    def test_hugepages_not_configured(self):
        self.node.attributes['hugepages']['nova'] = {'value': {}}
        self.check_fail('Hugepages for Nova are not configured')

    def test_hugepages_not_configured2(self):
        self.node.attributes['hugepages']['dpdk'] = {'value': '0'}
        self.check_fail('Hugepages for DPDK are not configured')

    def test_iface_cant_be_availible(self):
        props = self.data['interfaces'][0]['interface_properties']
        props['pci_id'] = 'test_id:2'

        dpdk = props.get('dpdk', {})
        dpdk['available'] = True
        props['dpdk'] = dpdk

        self.check_fail("DPDK .* can't be changed manually")

    def test_wrong_network(self):
        self.data['interfaces'][1]['assigned_networks'] = []
        self.check_fail('Only private network could be assigned')

    def test_change_pci_id(self):
        iface = self.data['interfaces'][1]
        iface['interface_properties']['pci_id'] = '123:345'
        self.check_fail("PCI-ID .* can't be changed manually")

    def test_bond_dpdk(self):
        nic_2 = self.data['interfaces'][1]
        nic_3 = self.data['interfaces'][2]

        nets = nic_2['assigned_networks']
        nic_2['assigned_networks'] = []
        nic_3['interface_properties']['dpdk']['enabled'] = True

        bond_data = {
            'type': "bond",
            'name': "ovs-bond0",
            'mode': "active-backup",
            'assigned_networks': nets,
            'interface_properties': {
                'mtu': None,
                'disable_offloading': True,
                'dpdk': {
                    'enabled': True,
                    'available': True
                }
            },
            'bond_properties': {
                'mode': "active-backup",
                'type__': "ovs"
            },
            'slaves': [
                {'name': nic_2['name']},
                {'name': nic_3['name']}
            ]
        }

        self.data['interfaces'].append(bond_data)
        self.assertNotRaises(errors.InvalidData,
                             self.validator, self.data)
