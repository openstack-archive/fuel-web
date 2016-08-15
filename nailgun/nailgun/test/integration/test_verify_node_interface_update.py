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
from nailgun import errors
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
                'editable_attributes': {
                    'common': {
                        'libvirt_type': {
                            'value': consts.HYPERVISORS.kvm,
                        }
                    }
                }
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
            'attributes': {
                'dpdk': {
                    'enabled': {'value': True}},
            },
            'meta': {
                'dpdk': {
                    'available': True,
                },
                'pci_id': "test_id:2"
            }
        }
        objects.NIC.update(nic_2, {
            'attributes': utils.dict_merge(
                nic_2.attributes, dpdk_settings['attributes']),
            'meta': utils.dict_merge(
                nic_2.meta, dpdk_settings['meta'])
        })

        dpdk_settings['attributes']['dpdk']['enabled']['value'] = False
        objects.NIC.update(nic_3, {
            'attributes': utils.dict_merge(
                nic_3.attributes, dpdk_settings['attributes']),
            'meta': utils.dict_merge(
                nic_3.meta, dpdk_settings['meta'])
        })

        self.cluster_attrs = objects.Cluster.get_editable_attributes(
            self.cluster_db)

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

    def test_wrong_network(self):
        self.data['interfaces'][1]['assigned_networks'] = []
        self.check_fail('Only private network could be assigned')

    def test_change_pci_id(self):
        iface = self.data['interfaces'][1]
        iface['meta']['pci_id'] = '123:345'
        self.check_fail("PCI-ID .* can't be changed manually")

    def test_wrong_mtu(self):
        iface = self.data['interfaces'][1]
        iface['attributes']['mtu']['value']['value'] = 1501
        self.check_fail("MTU size must be less than 1500 bytes")

    def test_non_default_mtu(self):
        iface = self.data['interfaces'][1]
        iface['attributes']['mtu']['value']['value'] = 1500
        self.assertNotRaises(errors.InvalidData,
                             self.validator, self.data)

    def _create_bond_data(self):
        nic_2 = self.data['interfaces'][1]
        nic_3 = self.data['interfaces'][2]

        nets = nic_2['assigned_networks']
        nic_2['assigned_networks'] = []
        nic_3['attributes']['dpdk']['enabled']['value'] = True

        bond_data = {
            'type': "bond",
            'name': "ovs-bond0",
            'mode': "active-backup",
            'assigned_networks': nets,
            'attributes': {
                'offloading': {
                    'disable': {
                        'value': True,
                        'label': 'Disable offloading',
                        'type': 'checkbox',
                        'weight': 10
                    },
                    'metadata': {
                        'label': 'Offloading',
                        'weight': 10
                    },
                    'offloading_modes': {
                        'description': 'Offloading modes',
                        'value': {},
                        'label': 'Offloading modes',
                        'type': 'offloading_modes',
                        'weight': 20
                    }
                },
                'mtu': {
                    'value': {
                        'value': None,
                        'label': 'MTU',
                        'type': 'number',
                        'weight': 10
                    },
                    'metadata': {
                        'label': 'MTU',
                        'weight': 20
                    }
                },
                'dpdk': {
                    'enabled': {
                        'value': True,
                        'label': 'DPDK enabled',
                        'type': 'checkbox',
                        'weight': 10
                    },
                    'metadata': {
                        'label': 'DPDK',
                        'weight': 40
                    }
                }
            },
            'bond_properties': {
                'mode': "active-backup",
                'type__': "dpdkovs"
            },
            'slaves': [
                {'name': nic_2['name']},
                {'name': nic_3['name']}
            ]
        }

        self.data['interfaces'].append(bond_data)
        return bond_data

    def test_bond_slaves(self):
        self._create_bond_data()
        self.assertNotRaises(errors.InvalidData,
                             self.validator, self.data)

    def test_bond_slaves_not_available_dpdk(self):
        self._create_bond_data()
        nic_3 = self.node.nic_interfaces[2]

        meta = {
            'dpdk': {'available': False},
            'pci_id': ''
        }
        objects.NIC.update(nic_3, {
            'meta': utils.dict_merge(nic_3.meta, meta)})

        self.assertRaisesRegexp(
            errors.InvalidData,
            "DPDK is not available .*",
            self.validator, self.data)
