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

import json
from netaddr import IPAddress
from netaddr import IPNetwork

from nailgun.api.models import NetworkGroup
from nailgun.test.base import BaseIntegrationTest


class TestNovaHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestNovaHandlers, self).setUp()
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True},
            ]
        )
        self.cluster = self.env.clusters[0]
        resp = self.env.nova_networks_get(self.cluster.id)
        self.nets = json.loads(resp.body)

    def find_net_by_name(self, name):
        for net in self.nets['networks']:
            if net['name'] == name:
                return net

    def test_network_checking(self):
        resp = self.env.nova_networks_put(self.cluster.id, self.nets)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')

        ngs_created = self.db.query(NetworkGroup).filter(
            NetworkGroup.name.in_([n['name'] for n in self.nets['networks']])
        ).all()
        self.assertEquals(len(ngs_created), len(self.nets['networks']))

    def test_network_checking_fails_if_admin_intersection(self):
        admin_ng = self.env.network_manager.get_admin_network_group()
        self.find_net_by_name('fixed')["cidr"] = admin_ng.cidr

        resp = self.env.nova_networks_put(self.cluster.id, self.nets,
                                          expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Address space intersection between networks: "
            "admin (PXE), fixed."
        )

    def test_network_checking_fails_if_admin_intersection_ip_range(self):
        admin_ng = self.env.network_manager.get_admin_network_group()
        cidr = IPNetwork(admin_ng.cidr)
        self.find_net_by_name('floating')['ip_ranges'] = [
            [str(IPAddress(cidr.first + 2)), str(IPAddress(cidr.last))]
        ]

        resp = self.env.nova_networks_put(self.cluster.id, self.nets,
                                          expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Address space intersection between networks: "
            "admin (PXE), floating."
        )

    def test_fails_if_netmask_for_public_network_not_set_or_not_valid(self):
        net_without_netmask = self.find_net_by_name('public')
        net_with_invalid_netmask = self.find_net_by_name('public')

        net_without_netmask['netmask'] = None
        net_with_invalid_netmask['netmask'] = '255.255.255.2'

        for net in [net_without_netmask, net_with_invalid_netmask]:
            resp = self.env.nova_networks_put(self.cluster.id,
                                              {'networks': [net]},
                                              expect_errors=True)
            self.assertEquals(resp.status, 202)
            task = json.loads(resp.body)
            self.assertEquals(task['status'], 'error')
            self.assertEquals(task['progress'], 100)
            self.assertEquals(task['name'], 'check_networks')
            self.assertEquals(
                task['message'], 'Invalid netmask for public network')

    def test_network_checking_fails_if_networks_cidr_intersection(self):
        self.find_net_by_name('management')["cidr"] = \
            self.find_net_by_name('storage')["cidr"]

        resp = self.env.nova_networks_put(self.cluster.id, self.nets,
                                          expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Address space intersection between "
            "networks: management, storage."
        )

    def test_network_checking_fails_if_untagged_intersection(self):
        self.find_net_by_name('public')["vlan_start"] = None
        self.find_net_by_name('management')["vlan_start"] = None
        self.env.nova_networks_put(self.cluster.id, self.nets)

        resp = self.env.cluster_changes_put(self.cluster.id)
        self.assertEquals(resp.status, 200)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'deploy')

        self.assertEquals(
            task['message'],
            'Some untagged networks are assigned to the same physical '
            'interface. You should assign them to different physical '
            'interfaces:\nNode "None": "management", "public"'
        )


class TestNeutronHandlersGre(BaseIntegrationTest):

    def setUp(self):
        super(TestNeutronHandlersGre, self).setUp()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [{
            "mac": "00:00:00:00:00:66",
            "max_speed": 1000,
            "name": "eth0",
            "current_speed": 1000
        }, {
            "mac": "00:00:00:00:00:77",
            "max_speed": 1000,
            "name": "eth1",
            "current_speed": None}])
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[
                {
                    'api': True,
                    'roles': ['controller'],
                    'pending_addition': True,
                    'meta': meta,
                    'mac': "00:00:00:00:00:66"
                }
            ]
        )
        self.cluster = self.env.clusters[0]
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.nets = json.loads(resp.body)

    def test_network_checking(self):
        resp = self.env.neutron_networks_put(self.cluster.id, self.nets)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        ngs_created = self.db.query(NetworkGroup).filter(
            NetworkGroup.name.in_([n['name'] for n in self.nets['networks']])
        ).all()
        self.assertEquals(len(ngs_created), len(self.nets['networks']))

    def test_network_checking_fails_if_network_is_at_admin_iface(self):
        node_db = self.env.nodes[0]
        resp = self.env.node_nics_get(node_db.id)

        ifaces = json.loads(resp.body)
        ifaces[1]["assigned_networks"], ifaces[0]["assigned_networks"] = \
            ifaces[0]["assigned_networks"], ifaces[1]["assigned_networks"]

        self.env.node_collection_nics_put(
            node_db.id,
            [{"interfaces": ifaces, "id": node_db.id}])

        resp = self.env.cluster_changes_put(self.cluster.id)
        self.assertEquals(resp.status, 200)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'deploy')
        self.assertEquals(
            task['message'].find(
                "Some networks are "
                "assigned to the same physical interface as "
                "admin (PXE) network. You should move them to "
                "another physical interfaces:"),
            0
        )

    def test_network_checking_fails_if_admin_intersection(self):
        admin_ng = self.env.network_manager.get_admin_network_group()
        self.nets['networks'][2]["cidr"] = admin_ng.cidr

        resp = self.env.neutron_networks_put(self.cluster.id, self.nets,
                                             expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Intersection with admin network(s) '10.20.0.0/24' found"
        )

    def test_network_checking_fails_if_untagged_intersection(self):
        for n in self.nets['networks']:
            n['vlan_start'] = None

        self.env.neutron_networks_put(self.cluster.id, self.nets)

        resp = self.env.cluster_changes_put(self.cluster.id)
        self.assertEquals(resp.status, 200)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'deploy')
        self.assertEquals(
            task['message'].find(
                "Some untagged networks are "
                "assigned to the same physical interface. "
                "You should assign them to "
                "different physical interfaces:"),
            0
        )

    def test_network_checking_fails_if_public_gateway_not_in_cidr(self):
        for n in self.nets['networks']:
            if n['name'] == 'public':
                n['gateway'] = '172.16.10.1'

        resp = self.env.neutron_networks_put(self.cluster.id, self.nets,
                                             expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Public gateway 172.16.10.1 is not in "
            "Public address space 172.16.0.0/24."
        )

    def test_network_checking_fails_if_public_float_range_not_in_cidr(self):
        for n in self.nets['networks']:
            if n['name'] == 'public':
                n['cidr'] = '172.16.10.0/24'
                n['gateway'] = '172.16.10.1'

        resp = self.env.neutron_networks_put(self.cluster.id, self.nets,
                                             expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Floating address range 172.16.0.130:172.16.0.254 is not in "
            "Public address space 172.16.10.0/24."
        )

    def test_network_checking_fails_if_network_ranges_intersect(self):
        for n in self.nets['networks']:
            if n['name'] == 'management':
                n['cidr'] = '192.168.1.0/24'

        resp = self.env.neutron_networks_put(self.cluster.id, self.nets,
                                             expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Intersection between network address spaces found:\n"
            "management, storage"
        )

    def test_network_checking_fails_if_internal_gateway_not_in_cidr(self):
        int = self.nets['neutron_parameters']['predefined_networks']['net04']
        int['L3']['gateway'] = '172.16.10.1'

        resp = self.env.neutron_networks_put(self.cluster.id, self.nets,
                                             expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Internal gateway 172.16.10.1 is not in "
            "Internal address space 192.168.111.0/24."
        )

    def test_network_checking_fails_if_internal_w_floating_intersection(self):
        int = self.nets['neutron_parameters']['predefined_networks']['net04']
        int['L3']['cidr'] = '172.16.0.128/26'
        int['L3']['gateway'] = '172.16.0.129'

        resp = self.env.neutron_networks_put(self.cluster.id, self.nets,
                                             expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Intersection between Internal CIDR and Floating range."
        )


class TestNeutronHandlersVlan(BaseIntegrationTest):

    def setUp(self):
        super(TestNeutronHandlersVlan, self).setUp()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [{
            "mac": "00:00:00:00:00:66",
            "max_speed": 1000,
            "name": "eth0",
            "current_speed": 1000
        }, {
            "mac": "00:00:00:00:00:77",
            "max_speed": 1000,
            "name": "eth1",
            "current_speed": None
        }, {
            "mac": "00:00:00:00:00:88",
            "max_speed": 1000,
            "name": "eth2",
            "current_speed": None}])
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'vlan'
            },
            nodes_kwargs=[
                {
                    'api': True,
                    'roles': ['controller'],
                    'pending_addition': True,
                    'meta': meta,
                    'mac': "00:00:00:00:00:66"
                }
            ]
        )
        self.cluster = self.env.clusters[0]
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.nets = json.loads(resp.body)

    def test_network_checking(self):
        resp = self.env.neutron_networks_put(self.cluster.id, self.nets)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        ngs_created = self.db.query(NetworkGroup).filter(
            NetworkGroup.name.in_([n['name'] for n in self.nets['networks']])
        ).all()
        self.assertEquals(len(ngs_created), len(self.nets['networks']))

    def test_network_checking_failed_if_private_paired_w_other_network(self):
        node_db = self.env.nodes[0]
        resp = self.env.node_nics_get(node_db.id)

        ifaces = json.loads(resp.body)
        priv_net = filter(
            lambda nic: (nic["name"] in ["private"]),
            ifaces[1]["assigned_networks"]
        )
        ifaces[1]["assigned_networks"].remove(priv_net[0])
        ifaces[2]["assigned_networks"].append(priv_net[0])

        self.env.node_collection_nics_put(
            node_db.id,
            [{"interfaces": ifaces, "id": node_db.id}])

        resp = self.env.cluster_changes_put(self.cluster.id)
        self.assertEquals(resp.status, 200)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'deploy')
        self.assertEquals(
            task['message'].find(
                "Some networks are "
                "assigned to the same physical interface as "
                "private network. You should move them to "
                "another physical interfaces:"),
            0
        )

    def test_network_checking_failed_if_networks_tags_in_neutron_range(self):
        for n in self.nets['networks']:
            if n['vlan_start']:
                n['vlan_start'] += 1000

        resp = self.env.neutron_networks_put(self.cluster.id, self.nets)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'].find(
                "Networks VLAN tags are in "
                "ID range defined for Neutron L2. "
                "You should assign VLAN tags that are "
                "not in Neutron L2 VLAN ID range:"),
            0
        )
