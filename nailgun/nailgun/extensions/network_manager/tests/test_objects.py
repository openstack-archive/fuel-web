# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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

from netaddr import IPNetwork

from nailgun import consts
from nailgun.db.sqlalchemy.models import NodeBondInterface
from nailgun import objects
from nailgun.test.base import BaseTestCase


class TestNetworkGroup(BaseTestCase):

    def test_upgrade_range_mask_from_cidr(self):
        cluster = self.env.create_cluster(api=False)
        ng = cluster.network_groups[0]
        objects.NetworkGroup._update_range_from_cidr(
            ng, "192.168.10.0/24")
        ip_range = ng.ip_ranges[0]
        self.assertEqual("192.168.10.1", ip_range.first)
        self.assertEqual("192.168.10.254", ip_range.last)

    def test_upgrade_range_mask_from_cidr_use_gateway(self):
        cluster = self.env.create_cluster(api=False)
        ng = cluster.network_groups[0]
        objects.NetworkGroup._update_range_from_cidr(
            ng, "192.168.10.0/24",
            use_gateway=True)
        ip_range = ng.ip_ranges[0]
        self.assertEqual("192.168.10.2", ip_range.first)
        self.assertEqual("192.168.10.254", ip_range.last)

    def test_get_default_networkgroup(self):
        ng = objects.NetworkGroup.get_default_admin_network()
        self.assertIsNotNone(ng)

    def test_is_untagged(self):
        cluster = self.env.create_cluster(api=False)
        admin_net = objects.NetworkGroup.get_default_admin_network()
        mgmt_net = objects.NetworkGroup.get_from_node_group_by_name(
            objects.Cluster.get_default_group(cluster).id,
            consts.NETWORKS.management)
        self.assertTrue(objects.NetworkGroup.is_untagged(admin_net))
        self.assertFalse(objects.NetworkGroup.is_untagged(mgmt_net))

    def test_get_by_node_group(self):
        cluster = self.env.create_cluster(api=False)
        new_ng = self.env.create_node_group(api=False, cluster_id=cluster.id)

        networks = objects.NetworkGroup.get_by_node_group(new_ng.id)
        expected_nets = [n for n in new_ng.networks if n.name !=
                         consts.NETWORKS.fuelweb_admin]
        self.assertItemsEqual(networks, expected_nets)


class TestBondObject(BaseTestCase):

    def setUp(self):
        super(TestBondObject, self).setUp()
        self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}])
        self.node = self.env.nodes[0]

    def test_assign_networks(self):
        data = {
            'name': 'bond0',
            'slaves': self.node.nic_interfaces,
            'node': self.node
        }
        bond = objects.Bond.create(data)
        self.node.bond_interfaces.append(bond)
        networks = objects.NetworkGroup.get_by_node_group(self.node.group_id)
        objects.Bond.assign_networks(bond, networks)

        expected_networks = [{'id': n.id, 'name': n.name} for n in networks]
        self.assertItemsEqual(bond.assigned_networks, expected_networks)

    def test_update_bond(self):
        data = {
            'name': 'bond0',
            'slaves': self.node.nic_interfaces,
            'node': self.node,
        }
        bond = objects.Bond.create(data)
        offloading_modes = bond.offloading_modes
        offloading_modes[0]['state'] = 'test'

        data = {
            'offloading_modes': offloading_modes
        }
        objects.Bond.update(bond, data)
        self.assertEqual(data['offloading_modes'], bond.offloading_modes)

    def test_get_bond_interfaces_for_all_nodes(self):
        node = self.env.nodes[0]
        node.bond_interfaces.append(
            NodeBondInterface(name='ovs-bond0',
                              slaves=node.nic_interfaces))
        self.db.flush()
        bond_interfaces = objects.Bond.get_bond_interfaces_for_all_nodes(
            self.env.clusters[0])
        self.assertEqual(len(bond_interfaces), 1)


class TestNICObject(BaseTestCase):

    def setUp(self):
        super(TestNICObject, self).setUp()

        self.cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}])

    def test_replace_assigned_networks(self):
        node = self.env.nodes[0]
        nic_1 = node.interfaces[0]
        nic_2 = node.interfaces[1]

        self.assertEqual(len(nic_1.assigned_networks), 4)
        self.assertEqual(len(nic_2.assigned_networks), 1)

        new_nets = nic_1.assigned_networks_list + nic_2.assigned_networks_list
        objects.NIC.assign_networks(nic_1, new_nets)
        objects.NIC.assign_networks(nic_2, [])

        self.assertEqual(len(nic_1.assigned_networks), 5)
        self.assertEqual(len(nic_2.assigned_networks), 0)

    def test_get_interfaces_not_in_mac_list(self):
        node = self.env.nodes[0]

        self.assertEqual(len(node.interfaces), 2)
        macs = [i.mac for i in node.interfaces]
        expected_mac = macs[0]

        interfaces = objects.NICCollection.get_interfaces_not_in_mac_list(
            node.id, [macs[1]])

        mac_list = [iface.mac for iface in interfaces]
        self.assertEqual(len(mac_list), 1)
        self.assertEqual(mac_list[0], expected_mac)

    def test_get_nic_interfaces_for_all_nodes(self):
        nodes = self.env.nodes
        interfaces = []
        for node in nodes:
            for inf in node.nic_interfaces:
                interfaces.append(inf)
        nic_interfaces = objects.NIC.get_nic_interfaces_for_all_nodes(
            self.env.clusters[0])
        self.assertEqual(len(nic_interfaces), len(interfaces))

    def test_update_offloading_modes(self):
        node = self.env.nodes[0]
        new_modes = [
            {'state': True, 'name': 'tx-checksumming', 'sub': [
                {'state': False, 'name': 'tx-checksum-sctp', 'sub': []},
                {'state': True, 'name': 'tx-checksum-ipv6', 'sub': []},
                {'state': None, 'name': 'tx-checksum-ipv4', 'sub': []}]},
            {'state': None, 'name': 'rx-checksumming', 'sub': []},
            {'state': True, 'name': 'new_offloading_mode', 'sub': []}]
        objects.NIC.update_offloading_modes(node.interfaces[0], new_modes)
        self.assertListEqual(node.interfaces[0].offloading_modes, new_modes)

    def test_update_offloading_modes_keep_states(self):
        node = self.env.nodes[0]
        old_modes = [
            {'state': True, 'name': 'tx-checksumming', 'sub': [
                {'state': False, 'name': 'tx-checksum-sctp', 'sub': []},
                {'state': True, 'name': 'tx-checksum-ipv6', 'sub':
                    [{'state': None, 'name': 'tx-checksum-ipv4', 'sub': []}]}]
             }]

        node.interfaces[0].offloading_modes = old_modes
        new_mode = {'state': True, 'name': 'new_offloading_mode', 'sub': []}
        new_modes = [
            {'state': True, 'name': 'tx-checksumming', 'sub': [
                {'state': True, 'name': 'tx-checksum-sctp', 'sub': []},
                {'state': True, 'name': 'tx-checksum-ipv6', 'sub':
                    [{'state': False, 'name': 'tx-checksum-ipv4', 'sub': []}]}]
             },
            new_mode
            ]

        objects.NIC.update_offloading_modes(node.interfaces[0], new_modes,
                                            keep_states=True)
        old_modes.append(new_mode)
        # States for old offloading modes should be preserved
        self.assertListEqual(node.interfaces[0].offloading_modes,
                             old_modes)


class TestIPAddrObject(BaseTestCase):

    def setUp(self):
        super(TestIPAddrObject, self).setUp()

        self.cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}])

    def test_get_ips_except_admin(self):
        node = self.env.nodes[0]
        self.env.network_manager.assign_admin_ips([node])
        self.env.network_manager.assign_ips(
            self.cluster, [node], consts.NETWORKS.management
        )
        for ip in objects.IPAddr.get_ips_except_admin(node):
            self.assertEqual(ip.network_data.name, consts.NETWORKS.management)

    def test_delete_by_node(self):
        self.env.create_node(api=False, cluster_id=self.cluster.id)
        self.env.network_manager.assign_ips(
            self.cluster, self.env.nodes, consts.NETWORKS.management
        )

        all_ips = list(objects.IPAddr.get_ips_except_admin())
        self.assertEqual(len(all_ips), 2)

        node = self.env.nodes[0]
        objects.IPAddr.delete_by_node(node.id)

        all_ips = list(objects.IPAddr.get_ips_except_admin())
        self.assertEqual(len(all_ips), 1)
        self.assertEqual(all_ips[0].node, self.env.nodes[1].id)

    def test_delete_by_network(self):
        node = self.env.nodes[0]
        self.env.network_manager.assign_ips(
            self.cluster, [node], consts.NETWORKS.management
        )
        ips = list(objects.IPAddr.get_ips_except_admin())
        self.assertEqual(len(ips), 1)

        mgmt_ng = self.env.network_manager.get_network_by_netname(
            consts.NETWORKS.management, self.cluster.network_groups)
        storage_ng = self.env.network_manager.get_network_by_netname(
            consts.NETWORKS.storage, self.cluster.network_groups)

        # Create db record with same IP but different network group
        node_ip = node.ip_addrs[0].ip_addr
        new_ip = {
            'network_data': storage_ng,
            'ip_addr': node_ip,
            'node': node.id
        }
        objects.IPAddr.create(new_ip)
        ips = list(objects.IPAddr.get_ips_except_admin())
        self.assertEqual(len(ips), 2)

        # Delete newly created IP, existing IP in mgmt ng should remain
        objects.IPAddr.delete_by_network(node_ip, storage_ng.id)

        ips = list(objects.IPAddr.get_ips_except_admin())
        self.assertEqual(len(ips), 1)
        self.assertEqual(ips[0].network, mgmt_ng.id)

    def test_get_distinct_in_list(self):
        self.env.create_node(api=False, cluster_id=self.cluster.id)
        self.env.network_manager.assign_ips(
            self.cluster, self.env.nodes, consts.NETWORKS.management
        )

        mgmt_ng = self.env.network_manager.get_network_by_netname(
            consts.NETWORKS.management, self.cluster.network_groups)
        mgmt_cidr = mgmt_ng.cidr

        mgmt_ips = [str(ip) for ip in IPNetwork(mgmt_cidr)]
        assigned_ips = [
            ip.ip_addr for ip in list(objects.IPAddr.get_ips_except_admin())
        ]

        db_ips = [
            ip[0] for ip in objects.IPAddr.get_distinct_in_list(mgmt_ips)
        ]
        vips = objects.IPAddr.get_assigned_vips_for_controller_group(
            self.cluster
        )
        vips = set(ip.ip_addr for ip in vips)

        # Exclude vips from results
        db_ips = set(db_ips) - vips
        self.assertItemsEqual(db_ips, assigned_ips)

    def test_get_by_ip_addr(self):
        ng = objects.NetworkGroup.model(name='test')
        self.db.add(ng)
        self.db.flush()

        addr = '10.20.0.10'
        ip_addr = objects.IPAddr.model(
            ip_addr=addr,
            network=ng.id
        )
        self.db.add(ip_addr)
        self.db.flush()

        found = objects.IPAddrCollection.get_all_by_addr(addr).first()
        self.assertIsNotNone(found)
        self.assertEqual(found.ip_addr, addr)

    def test_get_admin_ip_for_node_with_admin_net(self):
        netmanager = objects.Cluster.get_network_manager()
        node = self.env.nodes[0]
        with mock.patch.object(objects.NetworkGroup,
                               'get_default_admin_network') as get_mock:
            netmanager.get_admin_ip_for_node(node)
            self.assertEqual(get_mock.call_count, 1)

        default_admin_net = objects.NetworkGroup.get_default_admin_network()
        with mock.patch.object(objects.NetworkGroup,
                               'get_default_admin_network') as get_mock:
            self.env.network_manager.get_admin_ip_for_node(
                node,
                default_admin_net)
            self.assertEqual(get_mock.call_count, 0)

    def test_get_node_networks_with_admin_net(self):
        node = self.env.nodes[0]

        default_admin_net = objects.NetworkGroup.get_default_admin_network()
        with mock.patch.object(objects.NetworkGroup,
                               'get_default_admin_network') as get_mock:
            get_mock.return_value = default_admin_net
            self.env.network_manager.get_node_networks(node)
            self.assertEqual(get_mock.call_count, 1)

        with mock.patch.object(objects.NetworkGroup,
                               'get_default_admin_network') as get_mock:
            self.env.network_manager.get_node_networks(node, default_admin_net)
            self.assertEqual(get_mock.call_count, 0)
