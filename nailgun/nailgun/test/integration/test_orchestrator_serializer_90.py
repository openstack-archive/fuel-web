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

from oslo_serialization import jsonutils
import unittest2

from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun import plugins
from nailgun.utils import reverse

from nailgun.extensions.network_manager.serializers.neutron_serializers \
    import NeutronNetworkDeploymentSerializer90
from nailgun.extensions.network_manager.serializers.neutron_serializers \
    import NeutronNetworkTemplateSerializer90

from nailgun.test.integration import test_orchestrator_serializer_80


class TestSerializer90Mixin(object):
    env_version = "mitaka-9.0"
    task_deploy = True
    dpdk_bridge_provider = consts.NEUTRON_L23_PROVIDERS.ovs

    @classmethod
    def create_serializer(cls, cluster):
        serializer_type = deployment_serializers.get_serializer_for_cluster(
            cluster
        )
        return serializer_type(None)

    @staticmethod
    def _get_serializer(cluster):
        return deployment_serializers.DeploymentLCMSerializer()

    @staticmethod
    def _get_nodes_count_in_astute_info(nodes):
        """Count number of node in deployment info for LCM serializer

        As we are running 7.0 tests against 9.0 environments where
        LCM serializer is used we should consider difference in a number
        of elements in deployment info.
        Number of elements in deployment info for LCM serializer is equal
        with node's number in a cluster.

        :param nodes: array of cluster nodes
        :returns: expected number of elements in deployment info
        """
        return len(nodes)

    @staticmethod
    def _handle_facts(facts):
        """Handle deployment facts for LCM serializers

        As we are running 7.0 tests against 9.0 environments where
        LCM serializer is used it's not expected to have master node
        in the list of serialized nodes.

        :param facts: deployment info produced by LCM serializer
        :returns: deployment info without master node data
        """
        return [node for node in facts
                if node.get('roles') != [consts.TASK_ROLES.master]]


class TestDeploymentAttributesSerialization90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestDeploymentAttributesSerialization80
):

    def serialize(self):
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        return self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)

    def _assign_dpdk_to_nic(self, node, dpdk_nic, other_nic):
        node.attributes['cpu_pinning']['dpdk']['value'] = 2
        other_nets = other_nic.assigned_networks_list
        dpdk_nets = dpdk_nic.assigned_networks_list

        for i, net in enumerate(other_nets):
            if net['name'] == 'private':
                dpdk_nets.append(other_nets.pop(i))
                break
        objects.NIC.assign_networks(other_nic, other_nets)
        objects.NIC.assign_networks(dpdk_nic, dpdk_nets)

        objects.NIC.update(dpdk_nic, {
            'meta': {
                'dpdk': {'available': True},
                'pci_id': 'test_id:2'
            },
            'attributes': {'dpdk': {'enabled': {'value': True}}}
        })

    def _create_cluster_with_vxlan(self):
        release_id = self.cluster_db.release.id
        self.cluster = self.env.create(
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.tun,
                'release_id': release_id})
        self.cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        self.serializer = self.create_serializer(self.cluster_db)

    def _get_br_name_by_segmentation_type(self):
        if (self.cluster.network_config.segmentation_type ==
                consts.NEUTRON_SEGMENT_TYPES.vlan):
            return consts.DEFAULT_BRIDGES_NAMES.br_prv
        return consts.DEFAULT_BRIDGES_NAMES.br_mesh

    @mock.patch('nailgun.objects.Release.get_supported_dpdk_drivers')
    def _check_dpdk_serializing(self, drivers_mock, has_vlan_tag=False,
                                sriov=False, max_queues=0,
                                dpdk_cpu_pinning=0, nic_driver=None):
        drivers_mock.return_value = {
            'driver_1': ['test_id:1', 'test_id:2']
        }
        node = self.env.create_nodes_w_interfaces_count(
            1, 3,
            cluster_id=self.cluster_db.id,
            roles=['compute'])[0]

        node.interfaces[0].attributes['sriov']['enabled']['value'] = sriov

        if has_vlan_tag:
            objects.NetworkGroup.get_node_network_by_name(
                node, 'private').vlan_start = '103'

        other_nic = node.interfaces[0]
        dpdk_nic = node.interfaces[2]

        self._assign_dpdk_to_nic(node, dpdk_nic, other_nic)
        dpdk_interface_name = dpdk_nic.name
        dpdk_nic.meta['max_queues'] = max_queues
        if dpdk_cpu_pinning:
            node.attributes['cpu_pinning']['dpdk']['value'] = dpdk_cpu_pinning
        if nic_driver:
            dpdk_nic.driver = nic_driver

        objects.Cluster.prepare_for_deployment(self.cluster_db)

        br_name = self._get_br_name_by_segmentation_type()

        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        self.assertEqual(len(self._handle_facts(
            serialized_for_astute['nodes'])), 1)
        serialized_node = serialized_for_astute['nodes'][0]
        dpdk = serialized_node.get('dpdk')

        vendor_specific = {'datapath_type': 'netdev'}
        vlan_id = objects.NetworkGroup.get_node_network_by_name(
            node, 'private').vlan_start
        if br_name == consts.DEFAULT_BRIDGES_NAMES.br_mesh and vlan_id:
            vendor_specific['vlan_id'] = vlan_id

        self.assertIsNotNone(dpdk)
        self.assertTrue(dpdk.get('enabled'))

        transformations = serialized_node['network_scheme']['transformations']
        private_br = filter(lambda t: t.get('name') == br_name,
                            transformations)[0]
        dpdk_ports = filter(lambda t: t.get('name') == dpdk_interface_name,
                            transformations)
        all_ports = filter(lambda t: t.get('action') == 'add-port',
                           transformations)
        self.assertEqual(private_br.get('vendor_specific'),
                         vendor_specific)
        self.assertEqual(private_br.get('provider'), self.dpdk_bridge_provider)
        self.assertEqual(len(all_ports) - len(dpdk_ports),
                         len(other_nic.assigned_networks_list))
        self.assertEqual(len(dpdk_ports), 1)
        self.assertEqual(dpdk_ports[0]['bridge'], br_name)
        self.assertEqual(dpdk_ports[0].get('provider'),
                         consts.NEUTRON_L23_PROVIDERS.dpdkovs)

        interfaces = serialized_node['network_scheme']['interfaces']
        dpdk_interface = interfaces[dpdk_interface_name]
        vendor_specific = dpdk_interface.get('vendor_specific', {})
        if sriov:
            self.assertEqual(vendor_specific.get('dpdk_driver'), 'vfio-pci')
        else:
            self.assertEqual(vendor_specific.get('dpdk_driver'), 'driver_1')

        if max_queues > 1 and dpdk_cpu_pinning > 2:
            self.assertEqual(vendor_specific.get('max_queues'),
                             min(max_queues, dpdk_cpu_pinning - 1))
        else:
            self.assertFalse('max_queues' in vendor_specific)
        if nic_driver:
            self.assertEqual(dpdk_interface['mtu'],
                             consts.DEFAULT_MTU + consts.SIZE_OF_VLAN_TAG)

    def test_serialization_with_dpdk(self):
        self._check_dpdk_serializing()

    def test_serialization_with_dpdk_sriov(self):
        self._check_dpdk_serializing(sriov=True)

    def test_serialization_with_dpdk_vxlan(self):
        self._create_cluster_with_vxlan()
        self._check_dpdk_serializing()

    def test_serialization_with_dpdk_vxlan_with_vlan_tag(self):
        self._create_cluster_with_vxlan()
        self._check_dpdk_serializing(has_vlan_tag=True)

    def test_serialization_with_dpdk_with_i40e_driver(self):
        driver = 'i40e'
        dpdk_cpu_pinning = 4
        self._check_dpdk_serializing(nic_driver=driver,
                                     dpdk_cpu_pinning=dpdk_cpu_pinning)

    def test_serialization_with_dpdk_queues_limited_max_queues(self):
        max_queues = 2
        dpdk_cpu_pinning = 4
        self._check_dpdk_serializing(max_queues=max_queues,
                                     dpdk_cpu_pinning=dpdk_cpu_pinning)

    def test_serialization_with_dpdk_queues_limited_dpdk_cpu_pinning(self):
        max_queues = 4
        dpdk_cpu_pinning = 3
        self._check_dpdk_serializing(max_queues=max_queues,
                                     dpdk_cpu_pinning=dpdk_cpu_pinning)

    @mock.patch('nailgun.objects.Release.get_supported_dpdk_drivers')
    def _check_dpdk_bond_serializing(self, attributes, drivers_mock):
        drivers_mock.return_value = {
            'driver_1': ['test_id:1', 'test_id:2']
        }
        node = self.env.create_nodes_w_interfaces_count(
            1, 4,
            cluster_id=self.cluster_db.id,
            roles=['compute'])[0]

        node.attributes['hugepages'] = {
            'dpdk': {'type': 'number', 'value': 1024},
            'nova': {'type': 'custom_hugepages', 'value': {'2048': 1}}
        }
        node.attributes['cpu_pinning']['dpdk']['value'] = 3

        cluster_attrs = objects.Cluster.get_editable_attributes(node.cluster)
        cluster_attrs['common']['libvirt_type'].update(
            {'value': consts.HYPERVISORS.kvm})
        objects.Cluster.update_attributes(
            node.cluster, {'editable': cluster_attrs})

        for iface in node.interfaces:
            iface['meta'].update({'pci_id': 'test_id:1'})
            iface['meta']['dpdk']['available'] = True

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
        attributes.update(
            {'dpdk': {'enabled': {'value': True}}})
        bond_interface = {
            'name': bond_interface_name,
            'type': consts.NETWORK_INTERFACE_TYPES.bond,
            'slaves': nics_for_bond,
            'assigned_networks': networks_for_bond,
            'attributes': attributes}
        interfaces.append(bond_interface)
        self.env.node_nics_put(node.id, interfaces)

        serialized_for_astute = self.serialize()
        self.assertEqual(len(self._handle_facts(
            serialized_for_astute['nodes'])), 1)
        serialized_node = serialized_for_astute['nodes'][0]
        dpdk = serialized_node.get('dpdk')

        br_name = self._get_br_name_by_segmentation_type()
        vendor_specific = {'datapath_type': 'netdev'}
        if br_name == consts.DEFAULT_BRIDGES_NAMES.br_mesh:
            vendor_specific['vlan_id'] = \
                objects.NetworkGroup.get_node_network_by_name(
                    node, 'private').vlan_start

        self.assertIsNotNone(dpdk)
        self.assertTrue(dpdk.get('enabled'))
        transformations = serialized_node['network_scheme']['transformations']

        private_br = filter(lambda t: t.get('name') == br_name,
                            transformations)[0]
        dpdk_bonds = filter(lambda t: t.get('name') ==
                            bond_interface_name,
                            transformations)
        self.assertEqual(len(dpdk_bonds), 1)
        self.assertEqual(dpdk_bonds[0]['bridge'], br_name)
        self.assertEqual(
            private_br.get('vendor_specific'), vendor_specific)
        self.assertEqual(
            dpdk_bonds[0].get('provider'),
            consts.NEUTRON_L23_PROVIDERS.dpdkovs)
        self.assertEqual(
            dpdk_bonds[0].get('bond_properties').get('mode'),
            attributes.get('mode', {}).get('value', {}).get('value'))
        interfaces = serialized_node['network_scheme']['interfaces']
        for iface in nics_for_bond:
            dpdk_interface = interfaces[iface['name']]
            vendor_specific = dpdk_interface.get('vendor_specific', {})
            self.assertEqual(vendor_specific.get('dpdk_driver'), 'driver_1')

    def test_serialization_with_dpdk_on_bond(self):
        attributes = {
            'mode': {'value': {'value': consts.BOND_MODES.balance_slb}},
            'type__': {'value': consts.BOND_TYPES.dpdkovs}
        }

        self._check_dpdk_bond_serializing(attributes)

    def test_serialization_with_dpdk_on_lacp_bond(self):
        attributes = {
            'mode': {'value': {'value': consts.BOND_MODES.balance_tcp}},
            'lacp': {'value': {'value': 'active'}},
            'lacp_rate': {'value': {'value': 'fast'}},
            'xmit_hash_policy': {'value': {'value': 'layer2'}},
            'type__': {'value': consts.BOND_TYPES.dpdkovs}
        }
        self._check_dpdk_bond_serializing(attributes)

    def test_serialization_with_vxlan_dpdk_on_bond(self):
        self._create_cluster_with_vxlan()
        attributes = {
            'mode': {'value': {'value': consts.BOND_MODES.balance_slb}},
            'type__': {'value': consts.BOND_TYPES.dpdkovs},
        }
        self._check_dpdk_bond_serializing(attributes)

    def test_serialization_with_vxlan_dpdk_on_lacp_bond(self):
        self._create_cluster_with_vxlan()
        attributes = {
            'mode': {'value': {'value': consts.BOND_MODES.balance_tcp}},
            'lacp': {'value': {'value': 'active'}},
            'lacp_rate': {'value': {'value': 'fast'}},
            'xmit_hash_policy': {'value': {'value': 'layer2'}},
            'type__': {'value': consts.BOND_TYPES.dpdkovs}
        }
        self._check_dpdk_bond_serializing(attributes)

    def test_attributes_cpu_pinning(self):
        numa_nodes = [
            {'id': 0, 'memory': 2 ** 31, 'cpus': [1, 2, 3, 4]},
            {'id': 1, 'memory': 2 ** 31, 'cpus': [5, 6, 7, 8]}
        ]
        node = self.env.create_nodes_w_interfaces_count(
            1, 3,
            cluster_id=self.cluster_db.id,
            roles=['compute'])[0]

        other_nic = node.interfaces[0]
        dpdk_nic = node.interfaces[2]

        self._assign_dpdk_to_nic(node, dpdk_nic, other_nic)

        node.meta['numa_topology']['numa_nodes'] = numa_nodes
        node.attributes.update({
            'cpu_pinning': {
                'nova': {'value': 2},
                'dpdk': {'value': 2},
            }
        })
        serialized_for_astute = self.serialize()
        serialized_node = serialized_for_astute['nodes'][0]
        self.assertEqual(serialized_node['dpdk']['ovs_core_mask'], '0x2')
        self.assertEqual(serialized_node['dpdk']['ovs_pmd_core_mask'], '0x4')
        self.assertEqual(serialized_node['nova']['cpu_pinning'], [5, 6])
        node_name = objects.Node.get_slave_name(node)
        network_data = serialized_for_astute['common']['network_metadata']
        node_common_attrs = network_data['nodes'][node_name]
        self.assertTrue(node_common_attrs['nova_cpu_pinning_enabled'])

    def test_pinning_cpu_for_dpdk(self):
        numa_nodes = [
            {'id': 0, 'memory': 2 ** 31, 'cpus': [1, 2, 3, 4]},
            {'id': 1, 'memory': 2 ** 31, 'cpus': [5, 6, 7, 8]}
        ]
        node = self.env.create_nodes_w_interfaces_count(
            1, 3,
            cluster_id=self.cluster_db.id,
            roles=['compute'])[0]

        other_nic = node.interfaces[0]
        dpdk_nic = node.interfaces[2]

        self._assign_dpdk_to_nic(node, dpdk_nic, other_nic)

        node.meta['numa_topology']['numa_nodes'] = numa_nodes
        node.attributes.update({
            'cpu_pinning': {
                'dpdk': {'value': 2},
            }
        })
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)

        serialized_node = serialized_for_astute['nodes'][0]

        self.assertEqual(serialized_node['dpdk']['ovs_core_mask'], '0x2')
        self.assertEqual(serialized_node['dpdk']['ovs_pmd_core_mask'], '0x4')
        self.assertNotIn('cpu_pinning', serialized_node.get('nova', {}))

        node_name = objects.Node.get_slave_name(node)
        network_data = serialized_for_astute['common']['network_metadata']
        node_common_attrs = network_data['nodes'][node_name]
        self.assertFalse(node_common_attrs['nova_cpu_pinning_enabled'])

    def test_pinning_cpu_for_nova(self):
        numa_nodes = [
            {'id': 0, 'memory': 2 ** 31, 'cpus': [1, 2, 3, 4]},
            {'id': 1, 'memory': 2 ** 31, 'cpus': [5, 6, 7, 8]}
        ]
        node = self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['compute'])

        node.meta['numa_topology']['numa_nodes'] = numa_nodes
        node.attributes.update({
            'cpu_pinning': {
                'nova': {'value': 2},
            }
        })
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)

        serialized_node = serialized_for_astute['nodes'][0]

        self.assertNotIn('dpdk', serialized_node)
        self.assertEqual(serialized_node['nova']['cpu_pinning'], [1, 2])
        node_name = objects.Node.get_slave_name(node)
        network_data = serialized_for_astute['common']['network_metadata']
        node_common_attrs = network_data['nodes'][node_name]
        self.assertTrue(node_common_attrs['nova_cpu_pinning_enabled'])

    def test_attributes_override_core_mask(self):
        numa_nodes = [
            {'id': 0, 'memory': 2 ** 31, 'cpus': [1, 2, 3, 4]},
            {'id': 1, 'memory': 2 ** 31, 'cpus': [5, 6, 7, 8]}
        ]
        node = self.env.create_nodes_w_interfaces_count(
            1, 3,
            cluster_id=self.cluster_db.id,
            roles=['compute'])[0]

        other_nic = node.interfaces[0]
        dpdk_nic = node.interfaces[2]

        self._assign_dpdk_to_nic(node, dpdk_nic, other_nic)

        node.meta['numa_topology']['numa_nodes'] = numa_nodes
        node.attributes.update({
            'cpu_pinning': {
                'nova': {'value': 2},
                'dpdk': {'value': 2},
            },
            'dpdk': {
                'ovs_pmd_core_mask': '0x3',
                'ovs_core_mask': '0x1'
            }
        })
        serialized_for_astute = self.serialize()
        serialized_node = serialized_for_astute['nodes'][0]

        self.assertEqual(serialized_node['dpdk']['ovs_core_mask'], '0x1')
        self.assertEqual(serialized_node['dpdk']['ovs_pmd_core_mask'], '0x3')

    def test_dpdk_hugepages(self):
        numa_nodes = []
        for i in six.moves.range(3):
            numa_nodes.append({
                'id': i,
                'cpus': [i],
                'memory': 2 * 1024 ** 3
            })

        meta = {
            'numa_topology': {
                'supported_hugepages': [2048],
                'numa_nodes': numa_nodes
            }
        }
        node = self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['compute'],
            meta=meta)
        node.interfaces[0].attributes.get('dpdk', {}).get(
            'enabled', {})['value'] = True
        node.attributes.update({
            'hugepages': {
                'dpdk': {
                    'value': 1024},
                'nova': {
                    'value': {'2048': 1}}}}
        )
        serialized_for_astute = self.serialize()
        serialized_node = serialized_for_astute['nodes'][0]
        self.assertEquals(
            [1024, 1024, 1024],
            serialized_node['dpdk']['ovs_socket_mem'])
        self.assertTrue(serialized_node['nova']['enable_hugepages'])

    def test_attributes_no_hugepages_distribution_with_gig_hugepage(self):
        meta = {
            'numa_topology': {
                'supported_hugepages': [2048, 1048576],
                'numa_nodes': [
                    {'id': 0, 'memory': 2 ** 31, 'cpus': [1, 2, 3, 4]},
                    {'id': 1, 'memory': 2 ** 31, 'cpus': [5, 6, 7, 8]}],
            }
        }
        node = self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['compute'],
            meta=meta)
        node.attributes.update({
            'hugepages': {
                'nova': {
                    'type': 'custom_hugepages',
                    'value': {
                        '2048': 512,
                        '1048576': 1
                    }
                },
                'dpdk': {
                    'type': 'number',
                    'value': 512,
                }
            }
        })
        serialized_for_astute = self.serialize()
        serialized_node = serialized_for_astute['nodes'][0]
        self.assertNotIn('hugepages', serialized_node)

    def test_attributes_hugepages_distribution(self):
        meta = {
            'numa_topology': {
                'supported_hugepages': [2048, 1048576],
                'numa_nodes': [
                    {'id': 0, 'memory': 2 ** 31, 'cpus': [1, 2, 3, 4]},
                    {'id': 1, 'memory': 2 ** 31, 'cpus': [5, 6, 7, 8]}],
            }
        }
        node = self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['compute'],
            meta=meta)
        node.attributes.update({
            'hugepages': {
                'nova': {
                    'type': 'custom_hugepages',
                    'value': {
                        '2048': 512,
                    }
                },
                'dpdk': {
                    'type': 'number',
                    'value': 512,
                }
            }
        })
        serialized_for_astute = self.serialize()
        serialized_node = serialized_for_astute['nodes'][0]
        expected = [
            {'numa_id': 0, 'size': 2048, 'count': 512},
            {'numa_id': 1, 'size': 2048, 'count': 512},
        ]

        self.assertEqual(serialized_node['hugepages'], expected)

    def test_cpu_pinning_disabled(self):
        nodes_roles = [['compute'], ['controller']]
        for roles in nodes_roles:
            self.env.create_node(
                cluster_id=self.cluster_db.id,
                roles=roles)

        serialized_for_astute = self.serialize()

        for serialized_node in serialized_for_astute['nodes']:
            nova = serialized_node.get('nova', {})
            self.assertNotIn('cpu_pinning', nova)

            dpdk = serialized_node.get('dpdk', {})
            self.assertNotIn('ovs_core_mask', dpdk)
            self.assertNotIn('ovs_pmd_core_mask', dpdk)

        network_data = serialized_for_astute['common']['network_metadata']
        for node_attrs in six.itervalues(network_data['nodes']):
            self.assertFalse(node_attrs['nova_cpu_pinning_enabled'])

    def test_hugepages_disabled(self):
        nodes_roles = [['compute'], ['controller']]
        for roles in nodes_roles:
            self.env.create_node(
                cluster_id=self.cluster_db.id,
                roles=roles)

        serialized_for_astute = self.serialize()

        for serialized_node in serialized_for_astute['nodes']:
            nova = serialized_node.get('nova', {})
            self.assertFalse(nova.get('enable_hugepages', False))

            dpdk = serialized_node.get('dpdk', {})
            self.assertNotIn('ovs_socket_mem', dpdk)

            self.assertNotIn('hugepages', serialized_node)

        network_data = serialized_for_astute['common']['network_metadata']
        for node_attrs in six.itervalues(network_data['nodes']):
            self.assertFalse(node_attrs['nova_hugepages_enabled'])

    def test_immutable_metadata_key(self):
        node = self.env.create_node(
            api=True,
            cluster_id=self.cluster_db.id,
            pending_roles=['controller'],
            pending_addition=True)
        self.db.flush()
        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': node['id']}),
            jsonutils.dumps({'hostname': 'new-name'}),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        serialized_for_astute = self.serialize()
        network_data = serialized_for_astute['common']['network_metadata']
        for k, v in six.iteritems(network_data['nodes']):
            node = objects.Node.get_by_uid(v['uid'])
            self.assertEqual(objects.Node.permanent_id(node), k)

    def test_plugin_interface_attributes_in_network_schema(self):
        interface_offloading = [
            {
                'name': 'tx-checksumming',
                'state': True,
                'sub': [
                    {
                        'name': 'tx-checksum-ipv6',
                        'state': None,
                        'sub': []
                    }
                ]
            },
            {
                'name': 'rx-checksumming',
                'state': False,
                'sub': []
            }
        ]

        offloading_modes_states = {
            'tx-checksumming': True,
            'tx-checksum-ipv6': False,
            'rx-checksumming': None
        }

        node = self.env.create_node(
            cluster_id=self.cluster.id,
            roles=['controller']
        )
        self.env.create_plugin(
            name='test_plugin',
            package_version='5.0.0',
            cluster=self.cluster,
            nic_attributes_metadata={
                'attribute_a': {
                    'label': 'Interface attribute A',
                    'value': 'attribute_a_val'
                },
                'attribute_b': {
                    'label': 'Interface attribute B',
                    'value': 'attribute_b_val'
                }
            }
        )

        for nic_interface in node.nic_interfaces:
            # set default values in meta for offloadin modes
            nic_interface.meta['offloading_modes'] = interface_offloading
            # change offloading modes via attributes
            nic_interface.attributes.update({
                'offloading': {'modes': {'value': offloading_modes_states}},
                'mtu': {'value': {'value': 2000}},
            })
        self.db.flush()

        serialized_data = self.serialize()['nodes'][0]
        serialized_interfaces = serialized_data['network_scheme']['interfaces']
        for nic_interface in node.nic_interfaces:
            nic_name = nic_interface.name
            self.assertEqual(2000, serialized_interfaces[nic_name].get('mtu'))
            vendor_specific = serialized_interfaces[nic_name].get(
                'vendor_specific', {})
            self.assertEqual('attribute_a_val',
                             vendor_specific.get('attribute_a'))
            self.assertEqual('attribute_b_val',
                             vendor_specific.get('attribute_b'))
            self.assertDictEqual(
                {
                    'offload': {'tx-checksumming': True,
                                'tx-checksum-ipv6': False,
                                'rx-checksumming': None}
                },
                serialized_interfaces[nic_name].get('ethtool')
            )

    def test_plugin_bond_attributes_in_network_schema(self):
        node = self.env.create_nodes_w_interfaces_count(
            1, 2, **{'cluster_id': self.cluster_db.id,
                     'roles': ['controller']})[0]
        bond_config = {
            'type__': {'value': consts.BOND_TYPES.linux},
            'mode': {'value': {'value': consts.BOND_MODES.balance_rr}}}
        nic_names = [iface.name for iface in node.nic_interfaces]
        self.env.make_bond_via_api(
            'lnx_bond', '', nic_names, node.id, attrs=bond_config)
        self.env.create_plugin(
            name='test_plugin',
            package_version='5.0.0',
            cluster=self.cluster_db,
            bond_attributes_metadata={
                'attribute_a': {
                    'label': 'Bond attribute A',
                    'value': 'attribute_a_val'
                },
                'attribute_b': {
                    'label': 'Bond attribute B',
                    'value': 'attribute_b_val'
                }
            }
        )

        serialized_data = self.serialize()['nodes'][0]
        for t in serialized_data['network_scheme']['transformations']:
            if t.get('name') == 'lnx_bond':
                vendor_interface_properties = \
                    t.get('interface_properties').get('vendor_specific', {})
                self.assertEqual(
                    'attribute_a_val',
                    vendor_interface_properties.get('attribute_a')
                )
                self.assertEqual(
                    'attribute_b_val',
                    vendor_interface_properties.get('attribute_b')
                )


class TestDeploymentLCMSerialization90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.BaseDeploymentSerializer
):
    def setUp(self):
        super(TestDeploymentLCMSerialization90, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={
                'version': self.env_version,
                'operating_system': consts.RELEASE_OS.ubuntu
            },
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan})
        self.cluster_db = self.env.clusters[-1]
        self.node = self.env.create_node(
            cluster_id=self.cluster_db.id, roles=['compute']
        )
        self.initialize_serrializer()

    def initialize_serrializer(self):
        self.serializer = self.create_serializer(self.cluster_db)

    @classmethod
    def create_serializer(cls, cluster):
        return deployment_serializers.DeploymentLCMSerializer()

    def test_inject_provision_node_with_node_replaced_provisioning_info(self):
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        test_provisioning_info = {'test': 123}
        self.node.replaced_provisioning_info = test_provisioning_info
        data = {}
        self.serializer.inject_provision_info(self.node, data)
        self.assertIn('provision', data)
        self.assertEqual(test_provisioning_info, data['provision'])

    def test_openstack_configuration_in_serialized(self):

        self.env.create_openstack_config(
            cluster_id=self.cluster_db.id,
            configuration={
                'glance_config': 'value1',
                'nova_config': 'value1',
                'ceph_config': 'value1'
            }
        )
        self.env.create_openstack_config(
            cluster_id=self.cluster_db.id, node_role='compute',
            configuration={'ceph_config': 'value2'}
        )
        self.env.create_openstack_config(
            cluster_id=self.cluster_db.id, node_id=self.node.id,
            configuration={'nova_config': 'value3'}
        )
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized = self.serializer.serialize(self.cluster_db, [self.node])

        self.assertEqual(
            {'glance_config': 'value1',
             'nova_config': 'value3',
             'ceph_config': 'value2'},
            serialized['nodes'][0]['configuration']
        )

    def test_openstack_configuration_options_in_serialized(self):
        conf_options = {
            'apply_on_deploy': False
        }
        self.env.create_openstack_config(
            cluster_id=self.cluster_db.id,
            configuration={
                'glance_config': 'value1',
                'nova_config': 'value1',
                'ceph_config': 'value1',
                'configuration_options': conf_options
            }
        )
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized = self.serializer.serialize(self.cluster_db, [self.node])
        node_info = serialized['nodes'][0]
        self.assertIn('configuration', node_info)
        self.assertIn('configuration_options', node_info)
        self.assertNotIn('configuration_options', node_info['configuration'])
        self.assertEqual(conf_options, node_info['configuration_options'])

    def test_cluster_attributes_in_serialized(self):
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized = self.serializer.serialize(self.cluster_db, [self.node])
        release = self.cluster_db.release
        release_info = {
            'name': release.name,
            'version': release.version,
            'operating_system': release.operating_system,
        }
        cluster_info = {
            "id": self.cluster_db.id,
            "name": self.cluster_db.name,
            "fuel_version": self.cluster_db.fuel_version,
            "status": self.cluster_db.status,
            "mode": self.cluster_db.mode
        }
        self.assertEqual(cluster_info, serialized['common']['cluster'])
        self.assertEqual(release_info, serialized['common']['release'])

        self.assertEqual(['compute'], serialized['nodes'][0]['roles'])
        self.assertEqual(
            [consts.TASK_ROLES.master], serialized['nodes'][1]['roles']
        )

    def test_inactive_cluster_attributes_in_serialized(self):
        objects.OpenstackConfig.create({
            "cluster_id": self.cluster_db.id,
            "node_id": self.node.id,
            "node_role": "ceph-osd",
            "configuration": {},
        })
        objects.OpenstackConfig.disable_by_nodes([self.node])
        self.initialize_serrializer()
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized = self.serializer.serialize(self.cluster_db, [self.node])
        release = self.cluster_db.release
        release_info = {
            'name': release.name,
            'version': release.version,
            'operating_system': release.operating_system,
        }
        cluster_info = {
            "id": self.cluster_db.id,
            "name": self.cluster_db.name,
            "fuel_version": self.cluster_db.fuel_version,
            "status": self.cluster_db.status,
            "mode": self.cluster_db.mode
        }
        self.assertEqual(cluster_info, serialized['common']['cluster'])
        self.assertEqual(release_info, serialized['common']['release'])

        self.assertEqual(['compute'], serialized['nodes'][0]['roles'])
        self.assertEqual(
            [consts.TASK_ROLES.master], serialized['nodes'][1]['roles']
        )

    @mock.patch.object(
        plugins.adapters.PluginAdapterBase, 'repo_files',
        mock.MagicMock(return_value=True)
    )
    def test_plugins_in_serialized(self):
        releases = [
            {'repository_path': 'repositories/ubuntu',
             'version': self.env_version, 'os': 'ubuntu',
             'mode': ['ha', 'multinode'],
             'deployment_scripts_path': 'deployment_scripts/'}
        ]
        plugin1 = self.env.create_plugin(
            cluster=self.cluster_db,
            name='plugin_1',
            attributes_metadata={'attributes': {'name': 'plugin_1'}},
            package_version='4.0.0',
            releases=releases
        )
        plugin2 = self.env.create_plugin(
            cluster=self.cluster_db,
            name='plugin_2',
            attributes_metadata={'attributes': {'name': 'plugin_2'}},
            package_version='4.0.0',
            releases=releases
        )
        self.env.create_plugin(
            cluster=self.cluster_db,
            enabled=False,
            name='plugin_3',
            attributes_metadata={'attributes': {'name': 'plugin_3'}},
            package_version='4.0.0',
            releases=releases
        )

        self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['compute']
        )
        plugins_data = [
            {
                'name': p.name,
                'scripts': [{
                    'remote_url': p.master_scripts_path(self.cluster_db),
                    'local_path': p.slaves_scripts_path
                }],
                'repositories': [{
                    'type': 'deb',
                    'name': p.path_name,
                    'uri': p.repo_url(self.cluster_db),
                    'suite': '/',
                    'section': '',
                    'priority': 1100
                }]
            }
            for p in six.moves.map(plugins.wrap_plugin, [plugin1, plugin2])
        ]
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)

        self.assertIn('plugins', serialized['common'])
        self.datadiff(plugins_data, serialized['common']['plugins'],
                      compare_sorted=True)

    def test_serialize_with_customized(self):
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized = self.serializer.serialize(self.cluster_db, [self.node])

        objects.Cluster.replace_deployment_info(self.cluster_db, serialized)
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        cust_serialized = self.serializer.serialize(
            self.cluster_db, [self.node])
        self.assertEqual(serialized['common'], cust_serialized['common'])
        self.assertItemsEqual(serialized['nodes'], cust_serialized['nodes'])

    def test_provision_info_serialized(self):
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized = self.serializer.serialize(self.cluster_db, [self.node])
        node_info = next(x for x in serialized['nodes']
                         if x['uid'] == self.node.uid)
        self.assertIn('provision', node_info)
        node_provision_info = node_info['provision']
        # check that key options present in provision section
        self.assertIn('ks_meta', node_provision_info)
        self.assertIn('engine', serialized['common']['provision'])
        provision_info = serialized['common']['provision']
        self.assertIn('packages', provision_info)
        self.assertIsInstance(provision_info['packages'], list)

    def test_deleted_field_present_only_for_deleted_nodes(self):
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        self.node.pending_deletion = True
        serialized = self.serializer.serialize(self.cluster_db, [self.node])
        node_info = next(x for x in serialized['nodes']
                         if x['uid'] == self.node.uid)
        self.assertTrue(node_info['deleted'])
        self.node.pending_deletion = False
        serialized = self.serializer.serialize(self.cluster_db, [self.node])
        node_info = next(x for x in serialized['nodes']
                         if x['uid'] == self.node.uid)
        self.assertNotIn('deleted', node_info)

    def test_plugin_node_attributes_serialization(self):
        node = self.env.create_node(
            cluster_id=self.cluster_db.id,
            roles=['compute']
        )
        self.env.create_plugin(
            name='test_plugin',
            package_version='5.0.0',
            cluster=self.cluster,
            node_attributes_metadata={
                'test_plugin_section': {
                    'attribute_a': {
                        'label': 'Node attribute A',
                        'value': 'attribute_a_val'
                    },
                    'attribute_b': {
                        'label': 'Node attribute B',
                        'value': 'attribute_b_val'
                    }
                }
            }
        )
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, [node])['common']['nodes'][0]
        self.assertIn('test_plugin_section', serialized_for_astute)
        self.assertDictEqual(
            {
                'attribute_a': 'attribute_a_val',
                'attribute_b': 'attribute_b_val'
            },
            serialized_for_astute.get('test_plugin_section', {})
        )


class TestDeploymentHASerializer90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestDeploymentHASerializer80
):
    def test_glance_properties(self):
        self.check_no_murano_data()

    def test_ceph_keys(self):
        storage_attrs = self.serializer.get_common_attrs(
            self.cluster
        )['storage']
        expected_keys = (
            'fsid', 'mon_key', 'admin_key', 'bootstrap_osd_key', 'radosgw_key'
        )
        for ceph_key in expected_keys:
            self.assertIn(ceph_key, storage_attrs)

    def test_serialize_with_customized(self):
        cluster = self.env.clusters[0]
        serializer = self._get_serializer(cluster)

        objects.Cluster.prepare_for_deployment(cluster)
        serialized = serializer.serialize(cluster, cluster.nodes)
        objects.Cluster.replace_deployment_info(cluster, serialized)
        objects.Cluster.prepare_for_deployment(cluster)
        cust_serialized = serializer.serialize(cluster, cluster.nodes)

        self.assertEqual(serialized['common'], cust_serialized['common'])
        self.assertItemsEqual(serialized['nodes'], cust_serialized['nodes'])


class TestDeploymentTasksSerialization90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestDeploymentTasksSerialization80
):
    pass


class TestMultiNodeGroupsSerialization90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestMultiNodeGroupsSerialization80
):
    pass


class TestNetworkTemplateSerializer90CompatibleWith80(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.
        TestNetworkTemplateSerializer80CompatibleWith70
):
    general_serializer = NeutronNetworkDeploymentSerializer90
    template_serializer = NeutronNetworkTemplateSerializer90

    def check_vendor_specific_is_not_set(self, use_net_template=False):
        node = self.env.create_node(
            cluster_id=self.cluster.id,
            roles=['controller'], primary_tags=['controller']
        )
        objects.Cluster.set_network_template(
            self.cluster,
            self.net_template if use_net_template else None)
        objects.Cluster.prepare_for_deployment(self.cluster)
        serializer = deployment_serializers.get_serializer_for_cluster(
            self.cluster)
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        nm = objects.Cluster.get_network_manager(self.cluster)
        networks = nm.get_node_networks(node)
        endpoints = net_serializer.generate_network_scheme(
            node, networks)['endpoints']

        for name in endpoints:
            # Just 'provider_gateway' can be in 'vendor_specific'
            if endpoints[name].get('vendor_specific'):
                self.assertItemsEqual(['provider_gateway'],
                                      endpoints[name]['vendor_specific'])

    # This test is replaced as we have different attributes set in 9.0
    def test_multiple_node_roles_network_metadata_attrs(self):
        for node_data in self.serialized_for_astute:
            self.assertItemsEqual(
                node_data['network_metadata'], ['nodes', 'vips'])
            nodes = node_data['network_metadata']['nodes']
            for node_name, node_attrs in nodes.items():
                self.assertTrue(
                    {'uid', 'fqdn', 'name', 'user_node_name', 'swift_zone',
                     'node_roles', 'network_roles',
                     'nova_cpu_pinning_enabled'}.issubset(node_attrs)
                )
                node = objects.Node.get_by_uid(node_attrs['uid'])
                self.assertEqual(objects.Node.get_slave_name(node), node_name)
                self.assertEqual(node_attrs['uid'], node.uid)
                self.assertEqual(node_attrs['fqdn'],
                                 objects.Node.get_node_fqdn(node))
                self.assertEqual(node_attrs['name'], node_name)
                self.assertEqual(node_attrs['user_node_name'], node.name)
                self.assertEqual(node_attrs['swift_zone'], node.uid)
                self.assertEqual(node_attrs['nova_cpu_pinning_enabled'], False)

    @unittest2.skip(
        "'nodes' key was removed from 9.0 version serializer output, "
        "thus test bound to this data (that exists in parent test case class) "
        "must be skipped"
    )
    def test_network_not_mapped_to_nics_w_template(self):
        pass


class TestNetworkTemplateSerializer90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestNetworkTemplateSerializer80
):
    legacy_serializer = NeutronNetworkDeploymentSerializer90
    template_serializer = NeutronNetworkTemplateSerializer90

    def check_selective_gateway(self, use_net_template=False):
        node = self.env.create_node(
            cluster_id=self.cluster.id,
            roles=['controller'], primary_tags=['controller']
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
    test_orchestrator_serializer_80.TestSerializeInterfaceDriversData80
):
    pass


class TestSriovSerialization90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.BaseDeploymentSerializer
):
    def setUp(self, *args):
        super(TestSriovSerialization90, self).setUp()
        self.cluster_db = self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan,
                'status': consts.CLUSTER_STATUSES.new},
        )
        self.env.create_nodes_w_interfaces_count(
            nodes_count=1, if_count=3, cluster_id=self.cluster_db.id,
            pending_roles=['compute'], pending_addition=True)

    def serialize(self):
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serializer = self.create_serializer(self.cluster_db)
        return serializer.serialize(self.cluster_db, self.env.nodes)

    def test_nic_sriov_info_is_serialized(self):
        for nic in self.env.nodes[0].nic_interfaces:
            if not nic.assigned_networks_list:
                nic_sriov = nic
                nic.attributes['sriov'] = {
                    'enabled': {'value': True},
                    'numvfs': {'value': 8},
                    'physnet': {'value': 'new_physnet'}
                }
                nic.meta['sriov'] = {
                    'available': True,
                    'totalvfs': 8,
                    'pci_id': '1234:5678'
                }
                objects.NIC.update(
                    nic, {'attributes': nic.attributes, 'meta': nic.meta})
                break
        else:
            self.fail('NIC without assigned networks was not found')

        serialized = self.serialize()
        node0 = serialized['nodes'][0]
        common_attrs = serialized['common']
        self.assertEqual(
            common_attrs['quantum_settings']['supported_pci_vendor_devs'],
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
