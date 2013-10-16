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
from netaddr import IPNetwork

from nailgun.api.models import NetworkGroup
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestNovaHandlers(BaseIntegrationTest):

    def update_networks(self, cluster_id, networks, expect_errors=False):
        return self.app.put(
            reverse('NovaNetworkConfigurationHandler',
                    kwargs={'cluster_id': cluster_id}),
            json.dumps(networks),
            headers=self.default_headers,
            expect_errors=expect_errors)

    def test_network_checking(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True},
            ]
        )
        cluster = self.env.clusters[0]

        nets = self.env.generate_ui_networks(
            cluster.id
        )
        resp = self.update_networks(cluster.id, nets)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        ngs_created = self.db.query(NetworkGroup).filter(
            NetworkGroup.name.in_([n['name'] for n in nets['networks']])
        ).all()
        self.assertEquals(len(ngs_created), len(nets['networks']))

    def test_network_checking_fails_if_admin_intersection(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True},
            ]
        )
        cluster = self.env.clusters[0]
        nets = self.env.generate_ui_networks(cluster.id)
        admin_ng = self.env.network_manager.get_admin_network_group()
        nets['networks'][-1]["cidr"] = admin_ng.cidr
        resp = self.update_networks(cluster.id, nets, expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Intersection with admin "
            "network(s) '{0}' found".format(
                admin_ng.cidr
            )
        )

    def test_network_checking_fails_if_admin_intersection_ip_range(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True},
            ]
        )
        cluster = self.env.clusters[0]
        nets = self.env.generate_ui_networks(cluster.id)
        admin_ng = self.env.network_manager.get_admin_network_group()
        base = IPNetwork(admin_ng.cidr)
        base.prefixlen += 1
        start_range = str(base[0])
        end_range = str(base[-1])
        nets['networks'][1]['ip_ranges'] = [
            [start_range, end_range]
        ]
        resp = self.update_networks(cluster.id, nets, expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "IP range {0} - {1} in {2} network intersects with admin "
            "range of {3}".format(
                start_range, end_range,
                nets['networks'][1]['name'],
                admin_ng.cidr
            )
        )

    def test_network_checking_fails_if_amount_flatdhcp(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True},
            ]
        )
        cluster = self.env.clusters[0]

        nets = self.env.generate_ui_networks(
            cluster.id
        )
        nets['networks'][-1]["amount"] = 2
        nets['networks'][-1]["cidr"] = "10.0.0.0/23"
        resp = self.update_networks(cluster.id, nets, expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Network amount for '{0}' is more than 1 "
            "while using FlatDHCP manager.".format(
                nets['networks'][-1]["name"]))

    def test_fails_if_netmask_for_public_network_not_set_or_not_valid(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True}])
        cluster = self.env.clusters[0]

        net_without_netmask = self.env.generate_ui_networks(
            cluster.id)

        net_with_invalid_netmask = self.env.generate_ui_networks(
            cluster.id)

        del net_without_netmask['networks'][1]['netmask']
        net_with_invalid_netmask['networks'][1]['netmask'] = '255.255.255.2'

        for nets in [net_without_netmask, net_with_invalid_netmask]:
            resp = self.update_networks(cluster.id, nets, expect_errors=True)

            self.assertEquals(resp.status, 202)
            task = json.loads(resp.body)
            self.assertEquals(task['status'], 'error')
            self.assertEquals(task['progress'], 100)
            self.assertEquals(task['name'], 'check_networks')
            self.assertEquals(
                task['message'], 'Invalid netmask for public network')


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
        self.nets = self.env.generate_ui_neutron_networks(self.cluster.id)

    def update_networks(self, cluster_id, networks, expect_errors=False):
        return self.app.put(
            reverse('NeutronNetworkConfigurationHandler',
                    kwargs={'cluster_id': cluster_id}),
            json.dumps(networks),
            headers=self.default_headers,
            expect_errors=expect_errors)

    def test_network_checking(self):
        resp = self.update_networks(self.cluster.id, self.nets)
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
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={
                'node_id': node_db.id
            }),
            headers=self.default_headers
        )
        ifaces = json.loads(resp.body)
        ifaces[1]["assigned_networks"], ifaces[0]["assigned_networks"] = \
            ifaces[0]["assigned_networks"], ifaces[1]["assigned_networks"]
        self.app.put(
            reverse('NodeCollectionNICsHandler', kwargs={
                'node_id': node_db.id
            }),
            json.dumps([{"interfaces": ifaces, "id": node_db.id}]),
            headers=self.default_headers
        )

        #self.update_networks(self.cluster.id, self.nets)

        resp = self.app.put(
            reverse(
                'ClusterChangesHandler',
                kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers
        )

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
        self.nets['networks'][-1]["cidr"] = admin_ng.cidr

        resp = self.update_networks(self.cluster.id, self.nets,
                                    expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "Intersection with admin "
            "network(s) '{0}' found".format(
                admin_ng.cidr
            )
        )

    def test_network_checking_fails_if_admin_intersection_ip_range(self):
        admin_ng = self.env.network_manager.get_admin_network_group()
        base = IPNetwork(admin_ng.cidr)
        base.prefixlen += 1
        start_range = str(base[0])
        end_range = str(base[-1])
        self.nets['networks'][1]['ip_ranges'] = [
            [start_range, end_range]
        ]

        resp = self.update_networks(
            self.cluster.id, self.nets, expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'],
            "IP range {0} - {1} in {2} network intersects with admin "
            "range of {3}".format(
                start_range, end_range,
                self.nets['networks'][1]['name'],
                admin_ng.cidr
            )
        )

    def test_network_checking_fails_if_untagged_intersection(self):
        for n in self.nets['networks']:
            n['vlan_start'] = None

        self.update_networks(self.cluster.id, self.nets)

        resp = self.app.put(
            reverse(
                'ClusterChangesHandler',
                kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers
        )

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
                n['gateway'] = '172.16.2.1'

        resp = self.update_networks(self.cluster.id, self.nets)

        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'].find(
                "Public gateway 172.16.2.1 is not in Public "
                "address space"),
            0
        )

    def test_network_checking_fails_if_public_floating_not_in_cidr(self):
        for n in self.nets['networks']:
            if n['name'] == 'public':
                n['cidr'] = '172.16.2.0/24'
                n['gateway'] = '172.16.2.1'

        resp = self.update_networks(self.cluster.id, self.nets)

        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.assertEquals(
            task['message'].find(
                "Floating address range 172.16.1.131:172.16.1.254 "
                "is not in Public address space"),
            0
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
        self.nets = self.env.generate_ui_neutron_networks(self.cluster.id)

    def update_networks(self, cluster_id, networks, expect_errors=False):
        return self.app.put(
            reverse('NeutronNetworkConfigurationHandler',
                    kwargs={'cluster_id': cluster_id}),
            json.dumps(networks),
            headers=self.default_headers,
            expect_errors=expect_errors)

    def test_network_checking(self):
        resp = self.update_networks(self.cluster.id, self.nets)
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
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={
                'node_id': node_db.id
            }),
            headers=self.default_headers
        )
        ifaces = json.loads(resp.body)
        priv_net = filter(
            lambda nic: (nic["name"] in ["private"]),
            ifaces[1]["assigned_networks"]
        )
        ifaces[1]["assigned_networks"].remove(priv_net[0])
        ifaces[2]["assigned_networks"].append(priv_net[0])
        self.app.put(
            reverse('NodeCollectionNICsHandler', kwargs={
                'node_id': node_db.id
            }),
            json.dumps([{"interfaces": ifaces, "id": node_db.id}]),
            headers=self.default_headers
        )

        resp = self.app.put(
            reverse(
                'ClusterChangesHandler',
                kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers
        )

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
            n['vlan_start'] += 1000

        resp = self.update_networks(self.cluster.id, self.nets)
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
