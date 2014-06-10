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
import json

from mock import Mock
from mock import patch
from netaddr import IPAddress
from netaddr import IPNetwork
from netaddr import IPRange
from sqlalchemy import not_

import nailgun

from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import IPAddrRange
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeNICInterface
from nailgun.network.neutron import NeutronManager
from nailgun.network.nova_network import NovaNetworkManager
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
            [n.id for n in self.env.nodes],
            "management"
        )

        management_net = self.db.query(NetworkGroup).\
            filter(
                NetworkGroup.cluster_id == self.env.clusters[0].id
            ).filter_by(
                name='management'
            ).first()

        assigned_ips = []
        for node in self.env.nodes:
            ips = self.db.query(IPAddr).\
                filter_by(node=node.id).\
                filter_by(network=management_net.id).all()

            self.assertEquals(1, len(ips))
            self.assertEquals(
                True,
                self.env.network_manager.check_ip_belongs_to_net(
                    ips[0].ip_addr,
                    management_net
                )
            )
            assigned_ips.append(ips[0].ip_addr)

        # check for uniqueness of IPs:
        self.assertEquals(len(assigned_ips), len(list(set(assigned_ips))))

        # check it doesn't contain broadcast and other special IPs
        net_ip = IPNetwork(management_net.cidr)[0]
        gateway = management_net.gateway
        broadcast = IPNetwork(management_net.cidr)[-1]
        self.assertEquals(False, net_ip in assigned_ips)
        self.assertEquals(False, gateway in assigned_ips)
        self.assertEquals(False, broadcast in assigned_ips)

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
            [node_db.id],
            "management"
        )
        self.env.network_manager.assign_ips(
            [node_db.id],
            "management"
        )

        self.db.refresh(node_db)

        self.assertEquals(
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
        cluster = self.env.create_cluster(api=True)
        vip = self.env.network_manager.assign_vip(
            cluster['id'],
            "management"
        )
        vip2 = self.env.network_manager.assign_vip(
            cluster['id'],
            "management"
        )
        self.assertEquals(vip, vip2)

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
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')
        network_data = self.env.network_manager.get_node_networks(
            self.env.nodes[0]
        )

        self.assertEquals(len(network_data), 4)
        fixed_nets = filter(lambda net: net['name'] == 'fixed', network_data)
        self.assertEquals(fixed_nets, [])

    def test_ipaddr_joinedload_relations(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True, "api": True},
                {"pending_addition": True, "api": True}
            ]
        )

        self.env.network_manager.assign_ips(
            [n.id for n in self.env.nodes],
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
        self.env.network_manager.assign_admin_ips(node.id, 2)
        admin_ng_id = self.env.network_manager.get_admin_network_group_id()
        admin_network_range = self.db.query(IPAddrRange).\
            filter_by(network_group_id=admin_ng_id).all()[0]

        admin_ips = self.db.query(IPAddr).\
            filter_by(node=node.id).\
            filter_by(network=admin_ng_id).all()
        self.assertEquals(len(admin_ips), 2)
        map(
            lambda x: self.assertIn(
                IPAddress(x.ip_addr),
                IPRange(
                    admin_network_range.first,
                    admin_network_range.last
                )
            ),
            admin_ips
        )

    def test_assign_admin_ips_large_range(self):
        map(self.db.delete, self.db.query(IPAddrRange).all())
        admin_ng_id = self.env.network_manager.get_admin_network_group_id()
        mock_range = IPAddrRange(
            first='10.0.0.1',
            last='10.255.255.254',
            network_group_id=admin_ng_id
        )
        self.db.add(mock_range)
        self.db.commit()
        # Creating two nodes
        n1 = self.env.create_node()
        n2 = self.env.create_node()
        nc = zip([n1.id, n2.id], [2048, 2])

        # Assinging admin IPs on created nodes
        map(lambda (n, c): self.env.network_manager.assign_admin_ips(n, c), nc)

        # Asserting count of admin node IPs
        def asserter(x):
            n, c = x
            l = len(self.db.query(IPAddr).filter_by(network=admin_ng_id).
                    filter_by(node=n).all())
            self.assertEquals(l, c)
        map(asserter, nc)

    def test_assign_admin_ips_idempotent(self):
        node = self.env.create_node()
        self.env.network_manager.assign_admin_ips(node.id, 2)
        admin_net_id = self.env.network_manager.get_admin_network_group_id()
        admin_ips = set([i.ip_addr for i in self.db.query(IPAddr).
                         filter_by(node=node.id).
                         filter_by(network=admin_net_id).all()])
        self.env.network_manager.assign_admin_ips(node.id, 2)
        admin_ips2 = set([i.ip_addr for i in self.db.query(IPAddr).
                          filter_by(node=node.id).
                          filter_by(network=admin_net_id).all()])
        self.assertEquals(admin_ips, admin_ips2)

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
        self.env.network_manager.assign_admin_ips(node.id, 1)

        admin_net_id = self.env.network_manager.get_admin_network_group_id()

        admin_ips = self.db.query(IPAddr).\
            filter_by(node=node.id).\
            filter_by(network=admin_net_id).all()
        self.assertEquals(len(admin_ips), 1)
        self.assertEquals(admin_ips[0].ip_addr, '10.0.0.1')

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
        admin_nic_id = self.node_db.admin_interface.id
        admin_nets = [n.name for n in self.db.query(
            NodeNICInterface).get(admin_nic_id).assigned_networks_list]

        other_nic = self.db.query(NodeNICInterface).filter_by(
            node_id=self.node_db.id
        ).filter(
            not_(NodeNICInterface.id == admin_nic_id)
        ).first()
        other_nets = [n.name for n in other_nic.assigned_networks_list]

        nics = NovaNetworkManager.get_default_networks_assignment(self.node_db)

        def_admin_nic = [n for n in nics if n['id'] == admin_nic_id]
        def_other_nic = [n for n in nics if n['id'] == other_nic.id]

        self.assertEquals(len(def_admin_nic), 1)
        self.assertEquals(len(def_other_nic), 1)
        self.assertEquals(
            set(admin_nets),
            set([n['name'] for n in def_admin_nic[0]['assigned_networks']]))
        self.assertEquals(
            set(other_nets),
            set([n['name'] for n in def_other_nic[0]['assigned_networks']]))


class TestNeutronManager(BaseIntegrationTest):

    def check_networks_assignment(self, node_db):
        node_nics = self.db.query(NodeNICInterface).filter_by(
            node_id=node_db.id
        ).all()

        def_nics = NeutronManager.get_default_networks_assignment(node_db)

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
