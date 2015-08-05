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

import itertools

import mock
from mock import Mock
from mock import patch
from netaddr import IPAddress
from netaddr import IPNetwork
from netaddr import IPRange
from sqlalchemy import not_

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
from nailgun.network.neutron import NeutronManager
from nailgun.network.neutron import NeutronManager70
from nailgun.network.nova_network import NovaNetworkManager
from nailgun.network.nova_network import NovaNetworkManager70
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class BaseNetworkManagerTest(BaseIntegrationTest):
    def _create_ip_addrs_by_rules(self, cluster, rules):
        created_ips = []
        for net_group in cluster.network_groups:
            if net_group.name not in rules:
                continue
            vips_by_types = rules[net_group.name]
            for vip_type, ip_addr in vips_by_types.items():
                ip = IPAddr(
                    network=net_group.id,
                    ip_addr=ip_addr,
                    vip_type=vip_type,
                )
                self.db.add(ip)
                created_ips.append(ip)
        if created_ips:
            self.db.flush()
        return created_ips


class TestNetworkManager(BaseNetworkManagerTest):

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
            self.env.nodes,
            "management"
        )

        management_net = self.db.query(NetworkGroup).\
            filter(
                NetworkGroup.group_id ==
                objects.Cluster.get_default_group(self.env.clusters[0]).id
            ).filter_by(
                name='management'
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

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_assign_ips_idempotent(self, mocked_rpc):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {
                    "pending_addition": True,
                    "api": True,
                    "status": "discover"
                }
            ]
        )

        node_db = self.env.nodes[0]

        self.env.network_manager.assign_ips(
            [node_db],
            "management"
        )
        self.env.network_manager.assign_ips(
            [node_db],
            "management"
        )

        self.db.refresh(node_db)

        self.assertEqual(
            len(
                filter(
                    lambda n: n['name'] == 'management',
                    self.env.network_manager.get_node_networks(
                        node_db
                    )
                )
            ),
            1
        )

    def test_assign_vip_is_idempotent(self):
        self.env.create_cluster(api=True)
        vip = self.env.network_manager.assign_vip(
            self.env.clusters[0],
            "management"
        )
        vip2 = self.env.network_manager.assign_vip(
            self.env.clusters[0],
            "management"
        )
        self.assertEqual(vip, vip2)

    def test_get_node_networks_for_vlan_manager(self):
        cluster = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True},
            ]
        )
        networks_data = \
            {'networking_parameters': {'net_manager': 'VlanManager'}}
        resp = self.env.nova_networks_put(cluster['id'], networks_data)
        self.assertEqual(resp.json_body['status'], 'ready')
        network_data = self.env.network_manager.get_node_networks(
            self.env.nodes[0]
        )

        self.assertEqual(len(network_data), 5)
        fixed_nets = filter(lambda net: net['name'] == 'fixed', network_data)
        self.assertEqual(len(fixed_nets), 1)

    def test_assign_admin_ip_multiple_groups(self):
        self.env.create(
            cluster_kwargs={
                'api': False,
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[{}, {}]
        )
        node_group = self.env.create_node_group()
        self.env.nodes[1].group_id = node_group.json_body['id']
        self.db().flush()

        admin_net =\
            self.env.network_manager.get_admin_network_group(
                self.env.nodes[1].id
            )
        mock_range = IPAddrRange(
            first='9.9.9.1',
            last='9.9.9.254',
            network_group_id=admin_net.id
        )
        self.db.add(mock_range)
        self.db.commit()

        self.env.network_manager.assign_admin_ips(self.env.nodes)

        for n in self.env.nodes:
            admin_net = self.env.network_manager.get_admin_network_group(n.id)
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
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[{}, {}]
        )
        node_group = self.env.create_node_group()
        self.env.nodes[1].group_id = node_group.json_body['id']
        self.db().flush()
        mgmt_net = self.db.query(NetworkGroup).\
            filter(
                NetworkGroup.group_id == node_group.json_body["id"]
            ).filter_by(
                name='management'
            ).first()

        mock_range = IPAddrRange(
            first='9.9.9.1',
            last='9.9.9.254',
            network_group_id=mgmt_net.id
        )
        self.db.add(mock_range)
        self.db.commit()

        self.env.network_manager.assign_ips(self.env.nodes, "management")

        for n in self.env.nodes:
            mgmt_net = self.db.query(NetworkGroup).\
                filter(
                    NetworkGroup.group_id == n.group_id
                ).filter_by(
                    name='management'
                ).first()
            ip = self.db.query(IPAddr).\
                filter_by(network=mgmt_net.id).\
                filter_by(node=n.id).first()

            self.assertIn(
                IPAddress(ip.ip_addr),
                IPNetwork(mgmt_net.cidr)
            )

    def test_ipaddr_joinedload_relations(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True, "api": True},
                {"pending_addition": True, "api": True}
            ]
        )

        self.env.network_manager.assign_ips(
            self.env.nodes,
            "management"
        )

        ips = self.env.network_manager._get_ips_except_admin(joined=True)
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
        admin_ng_id = self.env.network_manager.get_admin_network_group_id()
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
        admin_net_id = self.env.network_manager.get_admin_network_group_id()
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
        admin_net_id = self.env.network_manager.get_admin_network_group_id()
        mock_range = IPAddrRange(
            first='10.0.0.1',
            last='10.0.0.1',
            network_group_id=admin_net_id
        )
        self.db.add(mock_range)
        self.db.commit()

        node = self.env.create_node()
        self.env.network_manager.assign_admin_ips([node])

        admin_net_id = self.env.network_manager.get_admin_network_group_id()

        admin_ips = self.db.query(IPAddr).\
            filter_by(node=node.id).\
            filter_by(network=admin_net_id).all()
        self.assertEqual(len(admin_ips), 1)
        self.assertEqual(admin_ips[0].ip_addr, '10.0.0.1')

    def test_assign_admin_ips_for_many_nodes(self):
        map(self.db.delete, self.db.query(IPAddrRange).all())
        admin_net_id = self.env.network_manager.get_admin_network_group_id()
        mock_range = IPAddrRange(
            first='10.0.0.1',
            last='10.0.0.2',
            network_group_id=admin_net_id
        )
        self.db.add(mock_range)
        self.db.commit()

        n1 = self.env.create_node()
        n2 = self.env.create_node()
        nc = [n1, n2]
        self.env.network_manager.assign_admin_ips(nc)

        admin_net_id = self.env.network_manager.get_admin_network_group_id()

        for node, ip in zip(nc, ['10.0.0.1', '10.0.0.2']):
            admin_ips = self.db.query(IPAddr).\
                filter_by(node=node.id).\
                filter_by(network=admin_net_id).all()
            self.assertEqual(len(admin_ips), 1)
            self.assertEqual(admin_ips[0].ip_addr, ip)

    def test_get_assigned_vips(self):
        vips_to_create = {
            'management': {
                'haproxy': '192.168.0.1',
                'vrouter': '192.168.0.2',
            },
            'public': {
                'haproxy': '172.16.0.2',
                'vrouter': '172.16.0.3',
            },
        }
        cluster = self.env.create_cluster(api=False)
        self._create_ip_addrs_by_rules(cluster, vips_to_create)
        vips = self.env.network_manager.get_assigned_vips(cluster)
        self.assertEqual(vips_to_create, vips)

    def test_assign_given_vips_for_net_groups(self):
        vips_to_create = {
            'management': {
                'haproxy': '192.168.0.1',
            },
            'public': {
                'haproxy': '172.16.0.2',
            },
        }
        vips_to_assign = {
            'management': {
                'haproxy': '192.168.0.1',
                'vrouter': '192.168.0.2',
            },
            'public': {
                'haproxy': '172.16.0.4',
                'vrouter': '172.16.0.5',
            },
        }
        cluster = self.env.create_cluster(api=False)
        self._create_ip_addrs_by_rules(cluster, vips_to_create)
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
            'management': {
                'haproxy': '10.10.0.1',
            },
        }
        expected_msg_regexp = '^Cannot assign VIP with the address "10.10.0.1"'
        cluster = self.env.create_cluster(api=False)
        with self.assertRaisesRegexp(errors.AssignIPError,
                                     expected_msg_regexp):
            self.env.network_manager.assign_given_vips_for_net_groups(
                cluster, vips_to_assign)

    def test_upgrade_range_mask_from_cidr(self):
        cluster = self.env.create_cluster(api=False)
        ng = cluster.network_groups[0]
        self.env.network_manager.update_range_mask_from_cidr(
            ng, "192.168.10.0/24")
        ip_range = ng.ip_ranges[0]
        self.assertEqual("192.168.10.1", ip_range.first)
        self.assertEqual("192.168.10.254", ip_range.last)

    def test_upgrade_range_mask_from_cidr_use_gateway(self):
        cluster = self.env.create_cluster(api=False)
        ng = cluster.network_groups[0]
        self.env.network_manager.update_range_mask_from_cidr(
            ng, "192.168.10.0/24",
            use_gateway=True)
        ip_range = ng.ip_ranges[0]
        self.assertEqual("192.168.10.2", ip_range.first)
        self.assertEqual("192.168.10.254", ip_range.last)

    def test_update_networks_idempotent(self):
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_l23_provider=consts.NEUTRON_L23_PROVIDERS.ovs,
        )
        get_network_config = network_configuration.\
            NeutronNetworkConfigurationSerializer.serialize_for_cluster
        nets = get_network_config(cluster)
        self.env.network_manager.update_networks(cluster, nets)
        updated_nets = get_network_config(cluster)
        self.assertEqual(nets, updated_nets)

    def test_update_networks(self):
        def get_net_by_name(networks, name):
            for net in networks:
                if net["meta"]["name"] == name:
                    return net
            raise Exception("Network with name {0} not found".format(name))

        updates = {
            "public": {
                "cidr": "172.16.42.0/24",
                "gateway": "172.16.42.1",
                "ip_ranges": [["172.16.42.2", "172.16.42.126"]],
            },
            "management": {
                'cidr': u'192.10.2.0/24',
                'ip_ranges': [[u'192.10.2.1', u'192.10.2.254']],
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
        for net_name, net_changes in updates.items():
            ng = get_net_by_name(nets["networks"], net_name)
            ng.update(net_changes)
        self.env.network_manager.update_networks(cluster, nets)
        updated_nets = get_network_config(cluster)
        for net_name in updates.keys():
            expected_ng = get_net_by_name(nets["networks"], net_name)
            updated_ng = get_net_by_name(updated_nets["networks"], net_name)
            self.assertEqual(expected_ng, updated_ng)

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

        admin_ng_id = self.env.network_manager.get_admin_network_group_id()
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


class TestNovaNetworkManager(BaseIntegrationTest):

    def setUp(self):
        super(TestNovaNetworkManager, self).setUp()
        self.env.create(
            cluster_kwargs={},
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
                'net_provider': 'neutron',
                'net_segment_type': 'gre'},
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True}
            ])

        self.check_networks_assignment(self.env.nodes[0])

    def test_tun_get_default_nic_assignment(self):
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'tun'},
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
                'net_provider': 'neutron',
                'net_segment_type': 'vlan'},
            nodes_kwargs=[
                {'api': True,
                 'meta': meta,
                 'pending_addition': True}
            ])

        self.check_networks_assignment(self.env.nodes[0])


class TestNeutronManager70(BaseNetworkManagerTest):

    def setUp(self):
        super(TestNeutronManager70, self).setUp()
        self.cluster = self._create_env()
        self.net_manager = objects.Cluster.get_network_manager(self.cluster)

    def _create_env(self):
        return self.env.create(
            release_kwargs={'version': '1111-7.0'},
            cluster_kwargs={
                'api': False,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron
            }
        )

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

    def test_get_network_group_for_role(self):
        net_template = self.env.read_fixtures(['network_template'])[0]
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
                          return_value=vip) as assign_vip_mock:
            endpoint_ip = self.net_manager.get_end_point_ip(self.cluster.id)
            assign_vip_mock.assert_called_once_with(
                self.cluster, mock.ANY, vip_type='public')
            self.assertEqual(endpoint_ip, vip)

    def test_assign_vips_for_net_groups_for_api(self):
        expected_aliases = [
            'management_vip', 'management_vrouter_vip',
            'public_vip', 'public_vrouter_vip'
        ]

        assigned_vips = self.net_manager.assign_vips_for_net_groups_for_api(
            self.cluster)

        self.assertItemsEqual(expected_aliases, assigned_vips.keys())

    def test_assign_vips_for_net_groups(self):
        expected_vips = [
            {'name': 'vrouter', 'namespace': 'vrouter'},
            {'name': 'vrouter_pub', 'namespace': 'vrouter'},
            {'name': 'management', 'namespace': 'haproxy'},
            {'name': 'public', 'namespace': 'haproxy'},
        ]

        assigned_vips = self.net_manager.assign_vips_for_net_groups(
            self.cluster)

        for vip in expected_vips:
            name = vip['name']
            self.assertIn(name, assigned_vips)
            self.assertEqual(assigned_vips[name]['namespace'],
                             vip['namespace'])
            self.assertEqual(assigned_vips[name]['node_roles'],
                             ['controller',
                              'primary-controller'])

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
        vips_to_create = {
            'management': {
                'vrouter': '192.168.0.1',
            },
            'public': {
                'vrouter_pub': '172.16.0.2',
            },
        }
        vips_to_assign = {
            'management': {
                'vrouter': '192.168.0.2',
                'management': '192.168.0.3',
            },
            'public': {
                'vrouter_pub': '172.16.0.4',
                'public': '172.16.0.5',
            },
        }
        self._create_ip_addrs_by_rules(self.cluster, vips_to_create)
        self.net_manager.assign_given_vips_for_net_groups(
            self.cluster, vips_to_assign)
        vips = self.net_manager.get_assigned_vips(self.cluster)
        self.assertEqual(vips_to_assign, vips)


class TestNovaNetworkManager70(TestNeutronManager70):

    def _create_env(self):
        return self.env.create(
            release_kwargs={'version': '1111-7.0'},
            cluster_kwargs={
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
                          return_value=vip) as assign_vip_mock:
            endpoint_ip = self.net_manager.get_end_point_ip(self.cluster.id)
            assign_vip_mock.assert_called_once_with(
                self.cluster, mock.ANY, vip_type='public')
            self.assertEqual(endpoint_ip, vip)
