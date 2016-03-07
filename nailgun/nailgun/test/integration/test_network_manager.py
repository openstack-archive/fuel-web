# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from copy import deepcopy
import itertools

import mock
from mock import Mock
from mock import patch
from netaddr import IPAddress
from netaddr import IPNetwork
from netaddr import IPRange
import six
from sqlalchemy import not_
import yaml

import nailgun
from nailgun import consts
from nailgun.errors import errors
from nailgun import objects
from nailgun.objects.serializers import network_configuration

from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import IPAddrRange
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun.db.sqlalchemy.models import Release
from nailgun.logger import logger
from nailgun.network.neutron import NeutronManager
from nailgun.network.neutron import NeutronManager70
from nailgun.network.neutron import NeutronManager80
from nailgun.network.nova_network import NovaNetworkManager
from nailgun.network.nova_network import NovaNetworkManager70
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class TestNetworkManager(BaseIntegrationTest):

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_assign_ips(self, mocked_rpc):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True, "api": True},
                {"pending_addition": True, "api": True}
            ]
        )

        nailgun.task.task.Cobbler = Mock()
        self.env.network_manager.assign_ips(
            self.env.clusters[-1],
            self.env.nodes,
            consts.NETWORKS.management
        )

        management_net = self.db.query(NetworkGroup).filter(
            NetworkGroup.group_id ==
            objects.Cluster.get_default_group(self.env.clusters[0]).id
        ).filter_by(
            name=consts.NETWORKS.management
        ).first()

        assigned_ips = []
        for node in self.env.nodes:
            ips = self.db.query(IPAddr).\
                filter_by(node=node.id).\
                filter_by(network=management_net.id).all()

            self.assertEqual(1, len(ips))
            self.assertEqual(
                True,
                self.env.network_manager.check_ip_belongs_to_net(
                    ips[0].ip_addr,
                    management_net
                )
            )
            assigned_ips.append(ips[0].ip_addr)

        # check for uniqueness of IPs:
        self.assertEqual(len(assigned_ips), len(list(set(assigned_ips))))

        # check it doesn't contain broadcast and other special IPs
        net_ip = IPNetwork(management_net.cidr)[0]
        gateway = management_net.gateway
        broadcast = IPNetwork(management_net.cidr)[-1]
        self.assertEqual(False, net_ip in assigned_ips)
        self.assertEqual(False, gateway in assigned_ips)
        self.assertEqual(False, broadcast in assigned_ips)

    def test_get_free_ips_from_ranges(self):
        ranges = [IPRange("192.168.33.2", "192.168.33.222")]

        ips = self.env.network_manager.get_free_ips_from_ranges(
            consts.NETWORKS.management, ranges, set(), 3
        )
        self.assertItemsEqual(["192.168.33.2", "192.168.33.3", "192.168.33.4"],
                              ips)

        self.db.add(IPAddr(ip_addr="192.168.33.3"))
        self.db.flush()
        ips = self.env.network_manager.get_free_ips_from_ranges(
            consts.NETWORKS.management, ranges, set(), 3
        )
        self.assertItemsEqual(["192.168.33.2", "192.168.33.4", "192.168.33.5"],
                              ips)

        ips = self.env.network_manager.get_free_ips_from_ranges(
            consts.NETWORKS.management, ranges,
            set(["192.168.33.5", "192.168.33.8"]), 7
        )
        self.assertItemsEqual(
            ["192.168.33.2", "192.168.33.4", "192.168.33.6", "192.168.33.7",
             "192.168.33.9", "192.168.33.10", "192.168.33.11"],
            ips)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_assign_ips_idempotent(self, mocked_rpc):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {
                    "pending_addition": True,
                    "api": True,
                    "status": consts.NODE_STATUSES.discover,
                }
            ]
        )

        node_db = self.env.nodes[0]
        self.env.network_manager.assign_ips(
            self.env.clusters[-1],
            [node_db],
            consts.NETWORKS.management
        )
        self.env.network_manager.assign_ips(
            self.env.clusters[-1],
            [node_db],
            consts.NETWORKS.management
        )

        self.db.refresh(node_db)

        self.assertEqual(
            len(
                filter(
                    lambda n: n['name'] == consts.NETWORKS.management,
                    self.env.network_manager.get_node_networks(
                        node_db
                    )
                )
            ),
            1
        )

    def test_assign_vip_is_idempotent(self):
        self.env.create_cluster(api=True)
        nodegroup = objects.Cluster.get_controllers_node_group(
            self.env.clusters[0])

        vip = self.env.network_manager.assign_vip(
            nodegroup,
            consts.NETWORKS.management,
            consts.NETWORK_VIP_NAMES_V6_1.haproxy
        )
        vip2 = self.env.network_manager.assign_vip(
            nodegroup,
            consts.NETWORKS.management,
            consts.NETWORK_VIP_NAMES_V6_1.haproxy
        )

        self.assertEqual(vip, vip2)

    def test_assign_vip_for_admin_network(self):
        self.env.create_cluster(api=True)
        nodegroup = objects.Cluster.get_controllers_node_group(
            self.env.clusters[0])

        self.env.network_manager.assign_vip(
            nodegroup,
            consts.NETWORKS.fuelweb_admin,
            consts.NETWORK_VIP_NAMES_V6_1.haproxy)

    def test_assign_vip_throws_not_found_exception(self):
        self.env.create_cluster(api=True)
        nodegroup = objects.Cluster.get_controllers_node_group(
            self.env.clusters[0])

        self.assertRaisesRegexp(
            errors.CanNotFindNetworkForNodeGroup,
            "Network 'non-existing-network' for nodegroup='[\w-]+' not found.",
            self.env.network_manager.assign_vip,
            nodegroup,
            'non-existing-network',
            consts.NETWORK_VIP_NAMES_V6_1.haproxy
        )

    def change_ranges_and_update_vip(self, vip):
        ip_range = vip.network_data.ip_ranges[0]

        new_first = '172.16.0.10'
        new_last = '172.16.0.20'

        # VIP address is outside of the new range
        new_vip_addr = '172.16.0.21'

        update_data = {
            'first': new_first,
            'last': new_last
        }
        objects.NailgunObject.update(ip_range, update_data)

        update_data = {
            'ip_addr': new_vip_addr,
            'is_user_defined': True
        }
        objects.IPAddr.update(vip, update_data)

    def get_cluster_and_vip(self):
        self.env.create_cluster(api=True)
        cluster = self.env.clusters[0]

        vip = objects.IPAddrCollection.get_by_cluster_id(cluster.id).first()

        return cluster, vip

    def test_assign_vip_return_user_defined_wo_namespace_outside_net(self):
        cluster, vip = self.get_cluster_and_vip()

        self.change_ranges_and_update_vip(vip)

        ip_before = vip.ip_addr

        self.env.network_manager.assign_vips_for_net_groups(cluster)

        vips_after = self.env.network_manager.get_assigned_vips(cluster)

        needed_vip_ip = [
            vip_info for network, vip_info in six.iteritems(vips_after)
            if vip.network_data.name == network and vip.vip_name in vip_info
        ][0][vip.vip_name]

        self.assertEqual(needed_vip_ip, ip_before)

    def test_assign_vip_throws_out_of_ips_error(self):
        cluster = self.env.create_cluster(api=False)
        pub_net = objects.NetworkGroup.get_by_cluster(cluster.id).filter(
            objects.NetworkGroup.model.name == consts.NETWORKS.public
        ).first()

        self.db.query(IPAddrRange).filter_by(
            network_group_id=pub_net.id
        ).delete()

        full_range = IPAddrRange(
            first='172.16.10.2',
            last='172.16.10.2',
            network_group_id=pub_net.id
        )
        self.db.add(full_range)
        self.db.flush()

        self.assertRaises(
            errors.OutOfIPs,
            self.env.network_manager.assign_vips_for_net_groups,
            cluster
        )

    def test_vip_for_admin_network_is_free(self):
        admin_net_id = objects.NetworkGroup.get_admin_network_group().id
        self.db.query(IPAddrRange).filter_by(
            network_group_id=admin_net_id
        ).delete()
        admin_range = IPAddrRange(
            first='10.20.0.3',
            last='10.20.0.254',
            network_group_id=admin_net_id
        )
        self.db.add(admin_range)
        self.db.flush()

        cluster = self.env.create(
            cluster_kwargs={"api": False},
            nodes_kwargs=[
                {"pending_addition": True, "api": True, "ip": "10.20.0.3"},
                {"pending_addition": True, "api": True, "ip": "10.20.0.4"},
                {"pending_addition": True, "api": True, "ip": "10.20.0.5"},
            ]
        )
        # These nodes are "bootstrapped". They have an IP but don't yet
        # belong to a cluster. Because fuelweb_admin is a shared network
        # these IPs should not be used for a VIP in any cluster.
        self.env.create_node(ip="10.20.0.6")
        self.env.create_node(ip="10.20.0.7")
        self.env.create_node(ip="10.20.0.8")

        self.env.network_manager.assign_admin_ips(cluster.nodes)
        admin_vip = self.env.network_manager.assign_vip(
            objects.Cluster.get_controllers_node_group(cluster),
            consts.NETWORKS.fuelweb_admin,
            consts.NETWORK_VIP_NAMES_V6_1.haproxy
        )

        node_ips = [n.ip for n in self.env.nodes]
        self.assertNotIn(admin_vip, node_ips)

    def test_get_node_networks_for_vlan_manager(self):
        cluster = self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network},
            nodes_kwargs=[
                {"pending_addition": True},
            ]
        )
        networks_data = {
            'networking_parameters': {
                'net_manager': consts.NOVA_NET_MANAGERS.VlanManager,
            },
        }
        resp = self.env.nova_networks_put(cluster['id'], networks_data)
        self.assertEqual(resp.status_code, 200)
        network_data = self.env.network_manager.get_node_networks(
            self.env.nodes[0]
        )

        self.assertEqual(len(network_data), 5)
        fixed_nets = filter(lambda net: net['name'] == consts.NETWORKS.fixed,
                            network_data)
        self.assertEqual(len(fixed_nets), 1)

    def test_assign_admin_ip_multiple_groups(self):
        self.env.create(
            cluster_kwargs={
                'api': False,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre,
            },
            nodes_kwargs=[{}, {}]
        )
        node_group = self.env.create_node_group()
        self.env.nodes[1].group_id = node_group.json_body['id']
        self.db().flush()

        admin_net =\
            objects.NetworkGroup.get_admin_network_group(
                self.env.nodes[1].id
            )
        mock_range = IPAddrRange(
            first='9.9.9.1',
            last='9.9.9.254',
            network_group_id=admin_net.id
        )
        self.db.add(mock_range)
        self.db.flush()

        self.env.network_manager.assign_admin_ips(self.env.nodes)

        for n in self.env.nodes:
            admin_net = objects.NetworkGroup.get_admin_network_group(n.id)
            ip = self.db.query(IPAddr).\
                filter_by(network=admin_net.id).\
                filter_by(node=n.id).first()

            self.assertIn(
                IPAddress(ip.ip_addr),
                IPNetwork(admin_net.cidr)
            )

    def test_assign_ip_multiple_groups(self):
        self.env.create(
            cluster_kwargs={
                'api': False,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre
            },
            nodes_kwargs=[{}, {}]
        )
        node_group = self.env.create_node_group()
        self.env.nodes[1].group_id = node_group.json_body['id']

        mgmt_net = self.db.query(NetworkGroup).filter_by(
            group_id=node_group.json_body['id'],
            name=consts.NETWORKS.management
        ).first()

        # set new range for management network of non-default node group
        mgmt_net.cidr = '7.7.7.0/24'
        mgmt_net.ip_ranges = [IPAddrRange(first='7.7.7.1', last='7.7.7.254')]
        self.db().flush()

        self.env.network_manager.assign_ips(
            self.env.clusters[-1],
            self.env.nodes,
            consts.NETWORKS.management
        )

        for node in self.env.nodes:
            mgmt_net = self.db.query(NetworkGroup).\
                filter_by(
                    group_id=node.group_id,
                    name=consts.NETWORKS.management).first()

            ip = self.db.query(IPAddr).\
                filter_by(network=mgmt_net.id, node=node.id).first()

            self.assertIn(IPAddress(ip.ip_addr), IPNetwork(mgmt_net.cidr))

    def test_ipaddr_joinedload_relations(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True, "api": True},
                {"pending_addition": True, "api": True}
            ]
        )

        self.env.network_manager.assign_ips(
            self.env.clusters[-1],
            self.env.nodes,
            consts.NETWORKS.management
        )

        ips = []
        for node in self.env.nodes:
            # if node_id is not passed to the method vips also will be
            # returned as they are assigned at the cretion of a cluster
            ip = objects.IPAddr.get_ips_except_admin(
                node_id=node.id, include_network_data=True
            )[0]
            ips.append(ip)

        self.assertEqual(len(ips), 2)
        self.assertTrue(isinstance(ips[0].node_data, Node))
        self.assertTrue(isinstance(ips[0].network_data, NetworkGroup))

    def test_nets_empty_list_if_node_does_not_belong_to_cluster(self):
        node = self.env.create_node(api=False)
        network_data = self.env.network_manager.get_node_networks(node)
        self.assertEqual(network_data, [])

    def test_assign_admin_ips(self):
        node = self.env.create_node()
        self.env.network_manager.assign_admin_ips([node])
        admin_ng_id = objects.NetworkGroup.get_admin_network_group().id
        admin_network_range = self.db.query(IPAddrRange).\
            filter_by(network_group_id=admin_ng_id).all()[0]

        admin_ip = self.db.query(IPAddr).\
            filter_by(node=node.id).\
            filter_by(network=admin_ng_id).all()
        self.assertEqual(len(admin_ip), 1)
        self.assertIn(
            IPAddress(admin_ip[0].ip_addr),
            IPRange(admin_network_range.first, admin_network_range.last))

    def test_assign_admin_ips_idempotent(self):
        node = self.env.create_node()
        self.env.network_manager.assign_admin_ips([node])
        admin_net_id = objects.NetworkGroup.get_admin_network_group().id
        admin_ips = set([i.ip_addr for i in self.db.query(IPAddr).
                         filter_by(node=node.id).
                         filter_by(network=admin_net_id).all()])
        self.env.network_manager.assign_admin_ips([node])
        admin_ips2 = set([i.ip_addr for i in self.db.query(IPAddr).
                          filter_by(node=node.id).
                          filter_by(network=admin_net_id).all()])
        self.assertEqual(admin_ips, admin_ips2)

    def test_assign_admin_ips_only_one(self):
        map(self.db.delete, self.db.query(IPAddrRange).all())
        admin_net_id = objects.NetworkGroup.get_admin_network_group().id
        mock_range = IPAddrRange(
            first='10.0.0.1',
            last='10.0.0.1',
            network_group_id=admin_net_id
        )
        self.db.add(mock_range)
        self.db.flush()

        node = self.env.create_node()
        self.env.network_manager.assign_admin_ips([node])

        admin_net_id = objects.NetworkGroup.get_admin_network_group().id

        admin_ips = self.db.query(IPAddr).\
            filter_by(node=node.id).\
            filter_by(network=admin_net_id).all()
        self.assertEqual(len(admin_ips), 1)
        self.assertEqual(admin_ips[0].ip_addr, '10.0.0.1')

    def test_assign_admin_ips_for_many_nodes(self):
        map(self.db.delete, self.db.query(IPAddrRange).all())
        admin_net_id = objects.NetworkGroup.get_admin_network_group().id
        mock_range = IPAddrRange(
            first='10.0.0.1',
            last='10.0.0.2',
            network_group_id=admin_net_id
        )
        self.db.add(mock_range)
        self.db.flush()

        n1 = self.env.create_node()
        n2 = self.env.create_node()
        nc = [n1, n2]
        self.env.network_manager.assign_admin_ips(nc)

        admin_net_id = objects.NetworkGroup.get_admin_network_group().id

        for node, ip in zip(nc, ['10.0.0.1', '10.0.0.2']):
            admin_ips = self.db.query(IPAddr).\
                filter_by(node=node.id).\
                filter_by(network=admin_net_id).all()
            self.assertEqual(len(admin_ips), 1)
            self.assertEqual(admin_ips[0].ip_addr, ip)

    def test_get_node_networks_ips(self):
        cluster = self.env.create_cluster(api=False)
        node = self.env.create_node(cluster_id=cluster.id)
        self.env.network_manager.assign_ips(
            cluster, [node], consts.NETWORKS.management
        )
        node_net_ips = dict(
            (ip.network_data.name, ip.ip_addr) for ip in node.ip_addrs
        )
        self.assertEquals(node_net_ips,
                          objects.Node.get_networks_ips_dict(node))

    def test_set_node_networks_ips(self):
        cluster = self.env.create_cluster(api=False)
        node = self.env.create_node(cluster_id=cluster.id)
        self.env.network_manager.assign_ips(
            cluster, [node], consts.NETWORKS.management
        )
        node_net_ips = \
            dict((net.name, self.env.network_manager.get_free_ips(net)[0])
                 for net in node.networks)
        objects.Node.set_networks_ips(node, node_net_ips)
        self.assertEquals(node_net_ips,
                          objects.Node.get_networks_ips_dict(node))

    def test_set_netgroups_ids(self):
        cluster = self.env.create_cluster(api=False)
        node = self.env.create_node(cluster_id=cluster.id)
        self.env.network_manager.assign_ips(
            cluster, [node], consts.NETWORKS.management
        )
        admin_ng_id = objects.NetworkGroup.get_admin_network_group(node.id).id
        node_ng_ids = dict((ip.network, admin_ng_id) for ip in node.ip_addrs)
        objects.Node.set_netgroups_ids(node, node_ng_ids)
        for ip in node.ip_addrs:
            self.assertEquals(admin_ng_id, ip.network)

    def test_set_nic_assignment_netgroups_ids(self):
        cluster = self.env.create_cluster(api=False)
        node = self.env.create_node(cluster_id=cluster.id)
        self.env.network_manager.assign_ips(
            cluster, [node], consts.NETWORKS.management
        )
        admin_ng_id = \
            objects.NetworkGroup.get_admin_network_group(node.id).id
        nic_ng_ids = \
            dict((net.id, admin_ng_id) for iface in node.nic_interfaces
                 for net in iface.assigned_networks_list)
        objects.Node.set_nic_assignment_netgroups_ids(node, nic_ng_ids)
        self.db.refresh(node)
        for iface in node.nic_interfaces:
            for net in iface.assigned_networks_list:
                self.assertEquals(admin_ng_id, net.id)

    def test_set_bond_assignment_netgroups_ids(self):
        cluster = self.env.create_cluster(api=False)
        node = self.env.create_node(cluster_id=cluster.id)
        self.env.network_manager.assign_ips(
            cluster, [node], consts.NETWORKS.management
        )
        assigned_networks = [net for iface in node.interfaces
                             for net in iface.assigned_networks]
        self.env.network_manager._update_attrs({
            'id': node.id,
            'interfaces': [{
                'name': 'ovs-bond0',
                'type': consts.NETWORK_INTERFACE_TYPES.bond,
                'mode': consts.BOND_MODES.balance_slb,
                'slaves': [{'name': 'eth0'}],
                'assigned_networks': assigned_networks
            }]
        })
        admin_ng_id = \
            objects.NetworkGroup.get_admin_network_group(node.id).id
        bond_ng_ids = \
            dict((net.id, admin_ng_id) for iface in node.bond_interfaces
                 for net in iface.assigned_networks_list)
        objects.Node.set_bond_assignment_netgroups_ids(node, bond_ng_ids)
        self.db.refresh(node)
        for iface in node.bond_interfaces:
            for net in iface.assigned_networks_list:
                self.assertEquals(admin_ng_id, net.id)

    def test_get_assigned_vips(self):
        vips_to_create = {
            consts.NETWORKS.management: {
                consts.NETWORK_VIP_NAMES_V6_1.haproxy: '192.168.0.1',
                consts.NETWORK_VIP_NAMES_V6_1.vrouter: '192.168.0.2',
            },
            consts.NETWORKS.public: {
                consts.NETWORK_VIP_NAMES_V6_1.haproxy: '172.16.0.2',
                consts.NETWORK_VIP_NAMES_V6_1.vrouter: '172.16.0.3',
            },
        }
        cluster = self.env.create_cluster(api=False)
        self.env.create_ip_addrs_by_rules(cluster, vips_to_create)
        vips = self.env.network_manager.get_assigned_vips(cluster)
        self.assertEqual(vips_to_create, vips)

    def test_assign_given_vips_for_net_groups(self):
        vips_to_assign = {
            consts.NETWORKS.management: {
                consts.NETWORK_VIP_NAMES_V6_1.haproxy: '192.168.0.1',
                consts.NETWORK_VIP_NAMES_V6_1.vrouter: '192.168.0.2',
            },
            consts.NETWORKS.public: {
                consts.NETWORK_VIP_NAMES_V6_1.haproxy: '172.16.0.4',
                consts.NETWORK_VIP_NAMES_V6_1.vrouter: '172.16.0.5',
            },
        }
        cluster = self.env.create_cluster(api=False)
        self.env.network_manager.assign_given_vips_for_net_groups(
            cluster, vips_to_assign)
        vips = self.env.network_manager.get_assigned_vips(cluster)
        self.assertEqual(vips_to_assign, vips)

    def test_assign_given_vips_for_net_groups_idempotent(self):
        cluster = self.env.create_cluster(api=False)
        self.env.network_manager.assign_vips_for_net_groups(cluster)
        expected_vips = self.env.network_manager.get_assigned_vips(cluster)
        self.env.network_manager.assign_given_vips_for_net_groups(
            cluster, expected_vips)
        self.env.network_manager.assign_vips_for_net_groups(cluster)
        vips = self.env.network_manager.get_assigned_vips(cluster)
        self.assertEqual(expected_vips, vips)

    def test_assign_given_vips_for_net_groups_assign_error(self):
        vips_to_assign = {
            consts.NETWORKS.management: {
                consts.NETWORK_VIP_NAMES_V6_1.haproxy: '10.10.0.1',
            },
        }
        expected_msg_regexp = '^Cannot assign VIP with the address "10.10.0.1"'
        cluster = self.env.create_cluster(api=False)
        with self.assertRaisesRegexp(errors.AssignIPError,
                                     expected_msg_regexp):
            self.env.network_manager.assign_given_vips_for_net_groups(
                cluster, vips_to_assign)

    def test_update_networks_idempotent(self):
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_l23_provider=consts.NEUTRON_L23_PROVIDERS.ovs,
        )
        get_network_config = network_configuration.\
            NeutronNetworkConfigurationSerializer.serialize_for_cluster
        nets = get_network_config(cluster)
        self.env.network_manager.update_networks(nets)
        updated_nets = get_network_config(cluster)
        self.assertEqual(nets, updated_nets)

    def get_net_by_name(self, networks, name):
        for net in networks:
            if net["meta"]["name"] == name:
                return net
        raise Exception("Network with name {0} not found".format(name))

    def test_update_networks(self):
        updates = {
            consts.NETWORKS.public: {
                "cidr": "172.16.42.0/24",
                "gateway": "172.16.42.1",
                "ip_ranges": [["172.16.42.2", "172.16.42.126"]],
            },
            consts.NETWORKS.management: {
                'cidr': "192.10.2.0/24",
                'ip_ranges': [["192.10.2.1", "192.10.2.254"]],
            },
        }
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_l23_provider=consts.NEUTRON_L23_PROVIDERS.ovs,
        )
        get_network_config = network_configuration.\
            NeutronNetworkConfigurationSerializer.serialize_for_cluster
        nets = get_network_config(cluster)
        for net_name, net_changes in six.iteritems(updates):
            ng = self.get_net_by_name(nets["networks"], net_name)
            ng.update(net_changes)
        self.env.network_manager.update_networks(nets)
        updated_nets = get_network_config(cluster)
        for net_name in updates.keys():
            expected_ng = self.get_net_by_name(nets["networks"], net_name)
            updated_ng = self.get_net_by_name(updated_nets["networks"],
                                              net_name)
            self.assertEqual(expected_ng, updated_ng)

    def test_update_networks_meta(self):
        updates = {
            consts.NETWORKS.public: {
                "meta": {"notation": consts.NETWORK_NOTATION.cidr},
            },
            consts.NETWORKS.management: {
                "meta": {"use_gateway": True}
            }
        }
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_l23_provider=consts.NEUTRON_L23_PROVIDERS.ovs,
        )

        get_network_config = network_configuration.\
            NeutronNetworkConfigurationSerializer.serialize_for_cluster
        nets = get_network_config(cluster)

        # Lower value of range is "192.168.0.1".
        mgmt_ng = self.get_net_by_name(
            nets["networks"],
            consts.NETWORKS.management)
        self.assertEqual(mgmt_ng['ip_ranges'][0][0], "192.168.0.1")

        for net_name, net_changes in six.iteritems(updates):
            ng = self.get_net_by_name(nets["networks"], net_name)
            ng['meta'].update(net_changes['meta'])

        self.env.network_manager.update_networks(nets)
        nets_updated = get_network_config(cluster)

        public_ng = self.get_net_by_name(
            nets_updated["networks"],
            consts.NETWORKS.public)
        self.assertEqual(public_ng["meta"]["notation"],
                         consts.NETWORK_NOTATION.cidr)

        mgmt_ng_updated = self.get_net_by_name(
            nets_updated["networks"],
            consts.NETWORKS.management)
        self.assertTrue(mgmt_ng_updated["meta"]["use_gateway"])

        # Check whether ranges are changed after 'use_gateway=True' was set.
        # Lower value of range is changed from "192.168.0.1" to "192.168.0.2".
        self.assertEqual(mgmt_ng_updated['ip_ranges'][0][0], "192.168.0.2")

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_admin_ip_cobbler(self, mocked_rpc):
        node_1_meta = {}
        self.env.set_interfaces_in_meta(node_1_meta, [{
            "name": "eth0",
            "mac": "00:00:00:00:00:00",
        }, {
            "name": "eth1",
            "mac": "00:00:00:00:00:01"}])
        node_2_meta = {}
        self.env.set_interfaces_in_meta(node_2_meta, [{
            "name": "eth0",
            "mac": "00:00:00:00:00:02",
        }, {
            "name": "eth1",
            "mac": "00:00:00:00:00:03"}])
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {
                    "api": True,
                    "pending_addition": True,
                    "mac": "00:00:00:00:00:00",
                    "meta": node_1_meta
                },
                {
                    "api": True,
                    "pending_addition": True,
                    "mac": "00:00:00:00:00:02",
                    "meta": node_2_meta
                }
            ]
        )

        self.env.launch_deployment()
        rpc_nodes_provision = nailgun.task.manager.rpc.cast. \
            call_args_list[0][0][1][0]['args']['provisioning_info']['nodes']

        admin_ng_id = objects.NetworkGroup.get_admin_network_group().id
        admin_network_range = self.db.query(IPAddrRange).\
            filter_by(network_group_id=admin_ng_id).all()[0]

        map(
            lambda (x, y): self.assertIn(
                IPAddress(
                    rpc_nodes_provision[x]['interfaces'][y]['ip_address']
                ),
                IPRange(
                    admin_network_range.first,
                    admin_network_range.last
                )
            ),
            itertools.product((0, 1), ('eth0',))
        )

    def test_restricted_networks(self):
        rel = self.env.create_release()
        enabled_net = {'name': 'always_enabled',
                       'notation': None,
                       'restrictions': ['false']}
        disabled_net = {'name': 'always_disabled',
                        'notation': None,
                        'restrictions': ['true']}
        netw_meta = deepcopy(rel.networks_metadata)
        netw_meta['neutron']['networks'].extend([enabled_net, disabled_net])
        rel.networks_metadata = netw_meta
        cluster = self.env.create_cluster(
            release_id=rel.id,
            api=False
        )
        self.assertEqual(len(filter(lambda ng: ng.name == 'always_enabled',
                                    cluster.network_groups)), 1)
        self.assertEqual(len(filter(lambda ng: ng.name == 'always_disabled',
                                    cluster.network_groups)), 0)

    def test_update_restricted_networks(self):
        restricted_net = {
            'name': 'restricted_net',
            'restrictions': [
                'settings:additional_components.ironic.value == false'
            ]
        }
        attributes_metadata = """
            editable:
                additional_components:
                    ironic:
                        value: %r
                        type: "checkbox"
        """
        rel = self.env.create_release()
        netw_meta = deepcopy(rel.networks_metadata)
        netw_meta['neutron']['networks'].append(restricted_net)
        rel.networks_metadata = netw_meta
        cluster = self.env.create_cluster(
            release_id=rel.id,
            api=False
        )
        self.env.create_node(cluster_id=cluster.id)
        self.assertEqual(len(filter(lambda ng: ng.name == 'restricted_net',
                                    cluster.network_groups)), 0)
        with patch.object(logger, 'warning') as mock_warn:
            objects.Cluster.patch_attributes(
                cluster, yaml.load(attributes_metadata % True))
            mock_warn.assert_called_once_with(
                "Cannot assign network %r appropriately for "
                "node %r. Set unassigned network to the "
                "interface %r",
                "restricted_net", mock.ANY, mock.ANY
            )
        assigned_nets_count = 0
        for iface in cluster.nodes[0].interfaces:
            assigned_nets_count += len(filter(lambda n: n['name'] ==
                                              'restricted_net',
                                              iface.assigned_networks))
        self.assertEqual(assigned_nets_count, 1)
        self.assertEqual(len(filter(lambda ng: ng.name == 'restricted_net',
                                    cluster.network_groups)), 1)
        objects.Cluster.patch_attributes(
            cluster, yaml.load(attributes_metadata % False))
        self.assertEqual(len(filter(lambda ng: ng.name == 'restricted_net',
                                    cluster.network_groups)), 0)

    def test_clear_assigned_networks(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True, "api": True},
            ]
        )

        node = self.env.nodes[0]
        self.env.network_manager.clear_assigned_networks(node)

        for iface in node.interfaces:
            self.assertEqual([], iface.assigned_networks_list)


class TestNovaNetworkManager(BaseIntegrationTest):

    def setUp(self):
        super(TestNovaNetworkManager, self).setUp()
        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network,
            },
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True}
            ])
        self.node_db = self.env.nodes[0]

    def test_get_default_nic_assignment(self):
        admin_nic_id = self.env.network_manager.get_admin_interface(
            self.node_db
        ).id
        admin_nets = [n.name for n in self.db.query(
            NodeNICInterface).get(admin_nic_id).assigned_networks_list]

        other_nic = self.db.query(NodeNICInterface).filter_by(
            node_id=self.node_db.id
        ).filter(
            not_(NodeNICInterface.id == admin_nic_id)
        ).first()
        other_nets = [n.name for n in other_nic.assigned_networks_list]

        nics = NovaNetworkManager.get_default_interfaces_configuration(
            self.node_db)

        def_admin_nic = [n for n in nics if n['id'] == admin_nic_id]
        def_other_nic = [n for n in nics if n['id'] == other_nic.id]

        self.assertEqual(len(def_admin_nic), 1)
        self.assertEqual(len(def_other_nic), 1)
        self.assertEqual(
            set(admin_nets),
            set([n['name'] for n in def_admin_nic[0]['assigned_networks']]))
        self.assertEqual(
            set(other_nets),
            set([n['name'] for n in def_other_nic[0]['assigned_networks']]))


class TestNeutronManager(BaseIntegrationTest):

    def check_networks_assignment(self, node_db):
        node_nics = self.db.query(NodeNICInterface).filter_by(
            node_id=node_db.id
        ).all()

        def_nics = NeutronManager.get_default_interfaces_configuration(node_db)

        self.assertEqual(len(node_nics), len(def_nics))
        for n_nic in node_nics:
            n_assigned = set(n['name'] for n in n_nic.assigned_networks)
            for d_nic in def_nics:
                if d_nic['id'] == n_nic.id:
                    d_assigned = set(n['name']
                                     for n in d_nic['assigned_networks']) \
                        if d_nic.get('assigned_networks') else set()
                    self.assertEqual(n_assigned, d_assigned)
                    break
            else:
                self.fail("NIC is not found")

    def test_gre_get_default_nic_assignment(self):
        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre},
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True}
            ])

        self.check_networks_assignment(self.env.nodes[0])

    def test_tun_get_default_nic_assignment(self):
        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.tun},
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True}
            ])

        self.check_networks_assignment(self.env.nodes[0])

    def test_vlan_get_default_nic_assignment(self):
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': '00:00:00:00:00:11'},
             {'name': 'eth1', 'mac': '00:00:00:00:00:22'},
             {'name': 'eth2', 'mac': '00:00:00:00:00:33'}])
        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan},
            nodes_kwargs=[
                {'api': True,
                 'meta': meta,
                 'pending_addition': True}
            ])

        self.check_networks_assignment(self.env.nodes[0])

    def test_admin_networks_serialization(self):
        cluster = self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre}
        )
        ng = self.env.create_node_group().json_body
        admin_nets = self.db.query(NetworkGroup).filter_by(
            name='fuelweb_admin'
        )
        admin_def = admin_nets.filter_by(group_id=None).first()
        admin_ng = admin_nets.filter_by(group_id=ng['id']).first()

        expected = [
            {
                'id': admin_def.id,
                'cidr': '10.20.0.0/24',
                'gateway': '10.20.0.1',
                'ip_ranges': [['10.20.0.129', '10.20.0.254']]
            },
            {
                'id': admin_ng.id,
                'cidr': '9.9.9.0/24',
                'gateway': '9.9.9.1',
                'ip_ranges': [['9.9.9.2', '9.9.9.254']]
            }
        ]

        nm = objects.Cluster.get_network_manager()
        admin_nets = nm.get_admin_networks()
        self.assertItemsEqual(admin_nets, expected)

        expected[0].update({
            'node_group_id': None,
            'node_group_name': None,
            'cluster_id': None,
            'cluster_name': None
        })
        expected[1].update({
            'node_group_id': ng['id'],
            'node_group_name': ng['name'],
            'cluster_id': cluster['id'],
            'cluster_name': cluster['name']
        })

        admin_nets = nm.get_admin_networks(True)
        self.assertItemsEqual(admin_nets, expected)

    def test_check_admin_network_mapping(self):
        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.tun},
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True}
            ])
        node = self.env.nodes[0]
        admin_nic = self.env.network_manager.get_admin_interface(node)
        # move 'pxe' flag to another interface
        for nic in node.nic_interfaces:
            if nic != admin_nic:
                admin_nic.pxe = False
                nic.pxe = True
                self.env.db.flush()
                admin_nic = nic
                break
        # networks mapping in DB is not changed
        self.assertNotEqual(
            admin_nic,
            self.env.network_manager.get_admin_interface(node))
        self.env.network_manager._remap_admin_network(node)
        # networks mapping in DB is changed
        self.assertEqual(
            admin_nic,
            self.env.network_manager.get_admin_interface(node))


class TestNeutronManager70(BaseIntegrationTest):

    def setUp(self):
        super(TestNeutronManager70, self).setUp()
        self.cluster = self._create_env()
        self.net_manager = objects.Cluster.get_network_manager(self.cluster)

    def _create_env(self):
        release = self._prepare_release()

        return self.env.create(
            cluster_kwargs={
                'api': False,
                'release_id': release.id,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron
            }
        )

    def _prepare_release(self):
        rel_id = self.env.create_release(version='1111-7.0').id
        rel_db = self.db.query(Release).filter_by(id=rel_id).one()

        to_patch = [
            {
                'id': "mgmt/vip",
                'default_mapping': "management",
                'properties': {
                    'subnet': True,
                    'gateway': False,
                    'vip': [
                        {
                            'name': "vrouter",
                            'namespace': "vrouter",
                            'alias': "management_vrouter_vip",
                        },
                        {
                            'name': "management",
                            'namespace': "haproxy",
                            'alias': "management_vip",
                        },
                    ]
                }
            },
            {
                'id': "public/vip",
                'default_mapping': "public",
                'properties': {
                    'subnet': True,
                    'gateway': True,
                    'vip': [
                        {
                            'name': "vrouter_pub",
                            'namespace': "vrouter",
                            'alias': "public_vrouter_vip",
                        },
                        {
                            'name': "public",
                            'namespace': "haproxy",
                            'alias': "public_vip",
                        }
                    ]
                }
            }
        ]

        rel_db.network_roles_metadata = to_patch
        self.db.flush()

        return rel_db

    def _check_vip_configuration(self, expected_vips, real_vips):
        for vip in expected_vips:
            name = vip['name']
            self.assertIn(name, real_vips)
            self.assertEqual(real_vips[name]['namespace'],
                             vip['namespace'])
            self.assertEqual(real_vips[name]['node_roles'],
                             ['controller',
                              'primary-controller'])

    def _get_network_role_metadata(self, **kwargs):
        network_role = {
            'id': 'test_network_role',
            'default_mapping': 'public',
            'properties': {
                'subnet': True,
                'gateway': False,
                'vip': [
                    {'name': 'test_vip_a'}
                ]
            }
        }
        network_role.update(kwargs)
        return network_role

    def test_get_network_manager(self):
        self.assertIs(self.net_manager, NeutronManager70)

    def test_purge_stalled_vips(self):
        vips_before = self.net_manager.get_assigned_vips(self.cluster)

        net_name = next(six.iterkeys(vips_before))
        vips_to_remove = vips_before[net_name]

        # remove network role information from release metadata in order
        # to omit processing of VIPs for this role
        new_nroles_meta = []
        for net_role in self.cluster.release.network_roles_metadata:
            if net_role.get('properties', {}).get('vip', []):
                vip_info = net_role['properties']['vip']
                if set(ip['name'] for ip in vip_info) == set(vips_to_remove):
                        continue
            new_nroles_meta.append(net_role)

        self.cluster.release.network_roles_metadata = new_nroles_meta

        self.net_manager.assign_vips_for_net_groups(self.cluster)
        vips_after = self.net_manager.get_assigned_vips(self.cluster)

        self.assertNotIn(net_name, vips_after)

        # check that information about VIPs for other networks is not affected
        # after purging
        del vips_before[net_name]
        self.assertEqual(vips_before, vips_after)

    def test_get_network_group_for_role(self):
        net_template = self.env.read_fixtures(['network_template_70'])[0]
        objects.Cluster.set_network_template(self.cluster, net_template)

        node_group = objects.Cluster.get_controllers_node_group(self.cluster)
        net_group_mapping = \
            self.net_manager.build_role_to_network_group_mapping(
                self.cluster, node_group.name)

        self.assertEqual(
            self.net_manager.get_network_group_for_role(
                self._get_network_role_metadata(id='public/vip'),
                net_group_mapping),
            'public')
        self.assertEqual(
            self.net_manager.get_network_group_for_role(
                self._get_network_role_metadata(id='keystone/api'),
                net_group_mapping),
            'management')
        self.assertEqual(
            self.net_manager.get_network_group_for_role(
                self._get_network_role_metadata(id='management'),
                net_group_mapping),
            'management')
        self.assertEqual(
            self.net_manager.get_network_group_for_role(
                self._get_network_role_metadata(
                    id='role_not_in_template',
                    default_mapping='default_net_group'), net_group_mapping),
            'default_net_group')

    def test_get_endpoint_ip(self):
        vip = '172.16.0.1'

        with patch.object(NeutronManager70, 'assign_vip',
                          return_value=Mock(ip_addr=vip)) as assign_vip_mock:
            endpoint_ip = self.net_manager.get_end_point_ip(self.cluster.id)
            assign_vip_mock.assert_called_once_with(
                objects.Cluster.get_controllers_node_group(self.cluster),
                mock.ANY, vip_name='public')
            self.assertEqual(endpoint_ip, vip)

    def assign_vips_for_api_and_check_configuration(self, allocate):
        expected_aliases = [
            'management_vip', 'management_vrouter_vip',
            'public_vip', 'public_vrouter_vip'
        ]

        expected_vips = [
            {'name': 'vrouter', 'namespace': 'vrouter'},
            {'name': 'vrouter_pub', 'namespace': 'vrouter'},
            {'name': 'management', 'namespace': 'haproxy'},
            {'name': 'public', 'namespace': 'haproxy'},
        ]

        assigned_vips = self.net_manager.assign_vips_for_net_groups_for_api(
            self.cluster, allocate=allocate)

        self._check_vip_configuration(expected_vips, assigned_vips['vips'])

        # Also check that the configuration in the old format is included
        for a in expected_aliases:
            self.assertIn(a, assigned_vips)

        return assigned_vips

    def check_assigned_vips_against_db_data(self, assigned_vips):
        vips_db = objects.IPAddrCollection.get_by_cluster_id(
            self.cluster.id
        )

        vip_info = assigned_vips['vips']
        for vip in vips_db:
            self.assertIn(vip.vip_name, vip_info)

            info = vip_info[vip.vip_name]
            self.assertEqual(info['ipaddr'], vip.ip_addr)
            self.assertEqual(info['is_user_defined'], vip.is_user_defined)

    def test_assign_vips_for_net_groups_for_api_w_allocation(self):
        assigned_vips = self.assign_vips_for_api_and_check_configuration(
            allocate=True)
        self.check_assigned_vips_against_db_data(assigned_vips)

    def test_assign_vips_for_net_groups_for_api_wo_allocation(self):
        # if anything, delete already assigned VIPs
        objects.IPAddrCollection.all().delete(synchronize_session='fetch')

        assigned_vips = self.assign_vips_for_api_and_check_configuration(
            allocate=False)

        # check that the action didn't triggered VIP allocation
        cluster_vips_db = objects.IPAddrCollection.get_by_cluster_id(
            self.cluster.id).all()
        self.assertFalse(cluster_vips_db)

        vip_info = assigned_vips['vips']
        for vip_name, info in six.iteritems(vip_info):
            self.assertIsNone(info['ipaddr'])
            self.assertFalse(info['is_user_defined'])

    def test_assign_vips_for_net_groups_for_api_contains_removed_vip(self):
        # allocate VIPs, if anything
        self.net_manager.assign_vips_for_net_groups(self.cluster)

        # remember details of removed VIP to check against them later
        removed_vip = objects.IPAddrCollection.get_by_cluster_id(
            self.cluster.id
        ).first()

        vip_name = removed_vip.vip_name

        self.db.delete(removed_vip)
        self.db.flush()

        assigned_vips = self.assign_vips_for_api_and_check_configuration(
            allocate=False)

        self.check_assigned_vips_against_db_data(assigned_vips)

        # check that removed VIP is serialized and it is done properly
        self.assertIn(vip_name, assigned_vips['vips'])
        self.assertIsNone(assigned_vips['vips'][vip_name]['ipaddr'])
        self.assertFalse(assigned_vips['vips'][vip_name]['is_user_defined'])

        # check that removed VIP is restored (as its info is present in
        # network roles metadata for the cluster) after auto allocation
        # executed
        assigned_vips = self.assign_vips_for_api_and_check_configuration(
            allocate=True)
        self.check_assigned_vips_against_db_data(assigned_vips)

    def test_assign_vips_for_net_groups(self):
        expected_vips = [
            {'name': 'vrouter', 'namespace': 'vrouter'},
            {'name': 'vrouter_pub', 'namespace': 'vrouter'},
            {'name': 'management', 'namespace': 'haproxy'},
            {'name': 'public', 'namespace': 'haproxy'},
        ]

        assigned_vips = self.net_manager.assign_vips_for_net_groups(
            self.cluster)

        self._check_vip_configuration(expected_vips, assigned_vips)

    @mock.patch('nailgun.objects.Cluster.get_network_roles')
    def test_check_unique_vip_names_for_cluster(self, get_nr_mock):
        fake_role_erroneous_data = [
            {
                'properties': {
                    'vip': [
                        {
                            'name': 'duplicate_name'
                        }
                    ]
                }
            },
            {
                'properties': {
                    'vip': [
                        {
                            'name': 'duplicate_name'
                        }
                    ]
                }
            },
        ]
        get_nr_mock.return_value = fake_role_erroneous_data
        self.assertRaises(
            errors.DuplicatedVIPNames,
            self.net_manager.check_unique_vip_names_for_cluster,
            self.cluster
        )

        fake_role_proper_data = [
            {
                'properties': {
                    'vip': [
                        {
                            'name': 'test_name_one'
                        }
                    ]
                }
            },
            {
                'properties': {
                    'vip': [
                        {
                            'name': 'test_name_two'
                        }
                    ]
                }
            },
        ]
        get_nr_mock.return_value = fake_role_proper_data
        self.assertNotRaises(
            errors.DuplicatedVIPNames,
            self.net_manager.check_unique_vip_names_for_cluster,
            self.cluster
        )

    def test_get_assigned_vips(self):
        self.net_manager.assign_vips_for_net_groups(self.cluster)
        vips = self.net_manager.get_assigned_vips(self.cluster)
        expected_vips = {
            'management': {
                'vrouter': '192.168.0.1',
                'management': '192.168.0.2',
            },
            'public': {
                'vrouter_pub': '172.16.0.2',
                'public': '172.16.0.3',
            },
        }
        self.assertEqual(expected_vips, vips)

    def test_assign_given_vips_for_net_groups(self):
        # rewrite VIPs allocated on creation of cluster
        vips_to_assign = {
            'management': {
                'vrouter': '192.168.0.4',
                'management': '192.168.0.5',
            },
            'public': {
                'vrouter_pub': '172.16.0.4',
                'public': '172.16.0.5',
            },
        }
        self.net_manager.assign_given_vips_for_net_groups(
            self.cluster, vips_to_assign)
        vips = self.net_manager.get_assigned_vips(self.cluster)
        self.assertEqual(vips_to_assign, vips)


class TestNovaNetworkManager70(TestNeutronManager70):

    def _create_env(self):
        release = self._prepare_release()

        return self.env.create(
            cluster_kwargs={
                'release_id': release.id,
                'api': False,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network
            }
        )

    def test_get_network_manager(self):
        self.assertIs(self.net_manager, NovaNetworkManager70)

    def test_get_network_group_for_role(self):
        node_group = objects.Cluster.get_controllers_node_group(self.cluster)
        net_group_mapping = \
            self.net_manager.build_role_to_network_group_mapping(
                self.cluster, node_group.name)

        self.assertEqual(
            self.net_manager.get_network_group_for_role(
                self._get_network_role_metadata(id='public/vip'),
                net_group_mapping),
            'public')
        self.assertEqual(
            self.net_manager.get_network_group_for_role(
                self._get_network_role_metadata(
                    id='role_not_in_template',
                    default_mapping='default_net_group'), net_group_mapping),
            'default_net_group')

    def test_get_endpoint_ip(self):
        vip = '172.16.0.1'

        with patch.object(NovaNetworkManager70, 'assign_vip',
                          return_value=Mock(ip_addr=vip)) as assign_vip_mock:
            endpoint_ip = self.net_manager.get_end_point_ip(self.cluster.id)
            assign_vip_mock.assert_called_once_with(
                objects.Cluster.get_controllers_node_group(self.cluster),
                mock.ANY, vip_name='public')
            self.assertEqual(endpoint_ip, vip)


class TestTemplateManager70(BaseIntegrationTest):
    def setUp(self):
        super(TestTemplateManager70, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={'version': '1111-7.0'},
            cluster_kwargs={
                'api': True,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
            }
        )
        self.cluster = objects.Cluster.get_by_uid(self.cluster['id'])
        self.nm = objects.Cluster.get_network_manager(self.cluster)
        self.net_template = self.env.read_fixtures(['network_template_70'])[1]
        self.env.create_nodes_w_interfaces_count(
            1, 5,
            roles=['controller'],
            cluster_id=self.cluster['id']
        )
        self.env._create_network_group(name='mongo', vlan_start=None)
        self.env._create_network_group(name='keystone', vlan_start=None)
        self.env._create_network_group(name='murano', vlan_start=None)
        objects.Cluster.set_network_template(
            self.cluster,
            self.net_template
        )

    def _get_network_by_name(self, name, cluster=None):
        cluster = cluster or self.env.clusters[0]
        return [n for n in cluster.network_groups if n.name == name][0]

    def _check_nic_mapping(self, node, expected_mapping):
        for nic in node.interfaces:
            assigned_nets = [net['name'] for net in nic.assigned_networks]
            self.assertItemsEqual(assigned_nets, expected_mapping[nic.name])

    def test_assign_networks_based_on_template(self):
        expected_mapping = {
            'eth0': ['fuelweb_admin'],
            'eth1': ['public', 'storage'],
            'eth2': ['murano'],
            'eth3': [],
            'eth4': ['mongo', 'keystone'],
            'eth5': [],
            'lnxbond0': ['management']
        }
        node = self.env.nodes[0]
        self._check_nic_mapping(node, expected_mapping)

        # Network groups should have their vlan updated to match what
        # is defined in the template.
        keystone_ng = self._get_network_by_name('keystone')
        self.assertEqual(keystone_ng.vlan_start, 202)

    def test_get_interfaces_from_template(self):
        expected_interfaces = {
            'br-aux': {
                'interface_properties': {},
                'name': 'eth3.103',
                'offloading_modes': [],
                'type': 'ether'
            },
            'br-ex': {
                'interface_properties': {},
                'name': 'eth1',
                'offloading_modes': [],
                'type': 'ether'
            },
            'br-fw-admin': {
                'interface_properties': {},
                'name': 'eth0',
                'offloading_modes': [],
                'type': 'ether'
            },
            'br-keystone': {
                'interface_properties': {},
                'name': 'eth4.202',
                'offloading_modes': [],
                'type': 'ether'
            },
            'br-mgmt': {
                'bond_properties': {'mode': u'active-backup'},
                'name': u'lnxbond0',
                'offloading_modes': [],
                'slaves': [{'name': u'eth3'}, {'name': u'eth4'}],
                'type': 'bond'
            },
            'br-mongo': {
                'interface_properties': {},
                'name': u'eth4.201',
                'offloading_modes': [],
                'type': 'ether'
            },
            'br-storage': {
                'interface_properties': {},
                'name': 'eth1.102',
                'offloading_modes': [],
                'type': 'ether'
            },
            'eth2': {
                'interface_properties': {},
                'name': 'eth2',
                'offloading_modes': [],
                'type': 'ether'
            },
            'eth3.101': {
                'interface_properties': {},
                'name': u'eth3.101',
                'offloading_modes': [],
                'type': 'ether'
            },
            'eth4.101': {
                'interface_properties': {},
                'name': u'eth4.101',
                'offloading_modes': [],
                'type': 'ether'
            }
        }

        interfaces = self.nm.get_interfaces_from_template(self.env.nodes[0])
        self.assertItemsEqual(interfaces, expected_interfaces)

    def test_reassign_networks_based_on_template(self):
        expected_mapping = {
            'eth0': ['fuelweb_admin'],
            'eth1': ['public', 'storage'],
            'eth2': ['murano'],
            'eth3': [],
            'eth4': ['mongo', 'keystone'],
            'eth5': [],
            'lnxbond0': ['management']
        }
        node = self.env.nodes[0]

        # All networks should be mapped as expected
        self._check_nic_mapping(node, expected_mapping)

        # When a network group is deleted it should be skipped
        # when the template is applied.
        keystone_ng = self._get_network_by_name('keystone')
        self.env._delete_network_group(keystone_ng.id)

        missing_net_mapping = expected_mapping.copy()
        missing_net_mapping['eth4'] = ['mongo']
        self._check_nic_mapping(node, missing_net_mapping)

        # Adding a new network group should reassign all networks on all
        # nodes based on the current template
        self.env._create_network_group(name='keystone', vlan_start=None)
        self._check_nic_mapping(node, expected_mapping)


class TestNeutronManager80(BaseIntegrationTest):

    def setUp(self):
        super(TestNeutronManager80, self).setUp()
        self.cluster = self._create_env()
        self.net_manager = objects.Cluster.get_network_manager(self.cluster)

    def _create_env(self):
        return self.env.create(
            release_kwargs={'version': '1111-8.0'},
            cluster_kwargs={
                'api': False,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron
            }
        )

    def _check_nic_mapping(self, node, expected_mapping):
        for nic in node.interfaces:
            assigned_nets = [net['name'] for net in nic.assigned_networks]
            self.assertItemsEqual(assigned_nets, expected_mapping[nic.name])

    def _check_vip_configuration(self, expected_vips, real_vips):
        for vip in expected_vips:
            name = vip['name']
            self.assertIn(name, real_vips)
            self.assertEqual(real_vips[name]['namespace'],
                             vip['namespace'])
            self.assertEqual(real_vips[name]['node_roles'],
                             ['controller',
                              'primary-controller'])
            self.assertIn('vendor_specific', real_vips[name].keys())
        expected_vips_names = sorted([vip['name'] for vip in expected_vips])
        self.assertListEqual(expected_vips_names, sorted(real_vips.keys()))

    def test_get_network_manager(self):
        self.assertIs(self.net_manager, NeutronManager80)

    def test_assign_vips_with_unmapped_net_groups(self):
        expected_vips = [
            {'name': 'vrouter', 'namespace': 'vrouter'},
            {'name': 'vrouter_pub', 'namespace': 'vrouter'},
            {'name': 'management', 'namespace': 'haproxy'},
            {'name': 'public', 'namespace': 'haproxy'},
        ]
        unmapped_roles = yaml.safe_load("""
- id: "unmapped_role"
  default_mapping: "non_existing_net"
  properties:
    subnet: true
    gateway: false
    vip:
       - name: "unmapped_vip"
         namespace: "haproxy"
        """)
        self.env._add_plugin_network_roles(self.cluster, unmapped_roles)
        assigned_vips = self.net_manager.assign_vips_for_net_groups(
            self.cluster)

        self.assertNotIn('unmapped_vip', assigned_vips)

        self._check_vip_configuration(expected_vips, assigned_vips)

    def test_network_template_vlan_bonds(self):
        expected_mapping = {
            'eth0': ['fuelweb_admin'],
            'eth1': [],
            'eth2': [],
            'bond0': ['storage', 'public', 'management', 'private'],
        }

        self.env.create_nodes_w_interfaces_count(
            1, 3,
            roles=['controller'],
            cluster_id=self.cluster['id']
        )
        node = self.env.nodes[0]
        net_template = self.env.read_fixtures(['network_template_80'])[2]
        objects.Cluster.set_network_template(
            self.cluster,
            net_template
        )

        self._check_nic_mapping(node, expected_mapping)
