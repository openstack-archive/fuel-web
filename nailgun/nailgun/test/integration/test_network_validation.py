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

from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestNetworkChecking(BaseIntegrationTest):

    def find_net_by_name(self, name):
        for net in self.nets['networks']:
            if net['name'] == name:
                return net

    def check_result_format(self, task):
        if task.get('result'):
            result = task['result']
            self.assertIsInstance(result, list)
            ng_fields = \
                NetworkGroup.__mapper__.columns.keys() + ["ip_ranges"]
            for res in result:
                if 'ids' in res:
                    self.assertIsInstance(res['ids'], list)
                if 'errors' in res:
                    self.assertIsInstance(res['errors'], list)
                    for f in res['errors']:
                        self.assertIn(f, ng_fields)

    def set_cluster_changes_w_error(self, cluster_id):
        resp = self.env.cluster_changes_put(cluster_id,
                                            expect_errors=True)
        self.assertEquals(resp.status, 200)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'deploy')
        self.check_result_format(task)
        return task

    def update_nova_networks_w_error(self, cluster_id, nets):
        resp = self.env.nova_networks_put(cluster_id, nets,
                                          expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.check_result_format(task)
        return task

    def update_nova_networks_success(self, cluster_id, nets):
        resp = self.env.nova_networks_put(cluster_id, nets)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        return task

    def update_neutron_networks_w_error(self, cluster_id, nets):
        resp = self.env.neutron_networks_put(cluster_id, nets,
                                             expect_errors=True)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'error')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        self.check_result_format(task)
        return task

    def update_neutron_networks_success(self, cluster_id, nets):
        resp = self.env.neutron_networks_put(cluster_id, nets)
        self.assertEquals(resp.status, 202)
        task = json.loads(resp.body)
        self.assertEquals(task['status'], 'ready')
        self.assertEquals(task['progress'], 100)
        self.assertEquals(task['name'], 'check_networks')
        return task


class TestNovaHandlers(TestNetworkChecking):

    def setUp(self):
        super(TestNovaHandlers, self).setUp()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {"name": "eth0", "mac": "00:00:00:00:00:66"},
            {"name": "eth1", "mac": "00:00:00:00:00:77"}])
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": True,
                 "meta": meta,
                 "pending_addition": True},
            ]
        )
        self.cluster = self.env.clusters[0]
        resp = self.env.nova_networks_get(self.cluster.id)
        self.nets = json.loads(resp.body)

    def test_network_checking(self):
        self.update_nova_networks_success(self.cluster.id, self.nets)

        ngs_created = self.db.query(NetworkGroup).filter(
            NetworkGroup.name.in_([n['name'] for n in self.nets['networks']])
        ).all()
        self.assertEquals(len(ngs_created), len(self.nets['networks']))

    def test_network_checking_fails_if_admin_intersection(self):
        admin_ng = self.env.network_manager.get_admin_network_group()
        self.find_net_by_name('fixed')["cidr"] = admin_ng.cidr

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            "Address space intersection between networks:\n",
            task['message'])
        self.assertIn("admin (PXE)", task['message'])
        self.assertIn("fixed", task['message'])

    def test_network_checking_fails_if_admin_intersection_ip_range(self):
        admin_ng = self.env.network_manager.get_admin_network_group()
        cidr = IPNetwork(admin_ng.cidr)
        self.find_net_by_name('floating')['ip_ranges'] = [
            [str(IPAddress(cidr.first + 2)), str(IPAddress(cidr.last))]
        ]

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            "Address space intersection between networks:\n",
            task['message'])
        self.assertIn("admin (PXE)", task['message'])
        self.assertIn("floating", task['message'])

    def test_fails_if_netmask_for_public_network_not_set_or_not_valid(self):
        net_without_netmask = self.find_net_by_name('public')
        net_with_invalid_netmask = self.find_net_by_name('public')

        net_without_netmask['netmask'] = None
        net_with_invalid_netmask['netmask'] = '255.255.255.2'

        for net in [net_without_netmask, net_with_invalid_netmask]:
            task = self.update_nova_networks_w_error(self.cluster.id,
                                                     {'networks': [net]})
            self.assertEquals(
                task['message'],
                'Invalid gateway or netmask for public network')

    def test_network_checking_fails_if_networks_cidr_intersection(self):
        self.find_net_by_name('management')["cidr"] = \
            self.find_net_by_name('storage')["cidr"]

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            "Address space intersection between networks:\n",
            task['message'])
        self.assertIn("management", task['message'])
        self.assertIn("storage", task['message'])

    def test_network_checking_fails_if_untagged_intersection(self):
        self.find_net_by_name('management')["vlan_start"] = None
        self.env.nova_networks_put(self.cluster.id, self.nets)

        task = self.set_cluster_changes_w_error(self.cluster.id)
        self.assertIn(
            'Some untagged networks are assigned to the same physical '
            'interface. You should assign them to different physical '
            'interfaces. Affected:\n',
            task['message'])
        self.assertIn('"management"', task['message'])
        self.assertIn(' networks at node "Untitled', task['message'])

    def test_network_checking_fails_if_networks_cidr_range_intersection(self):
        self.find_net_by_name('public')["ip_ranges"] = \
            [['192.18.17.65', '192.18.17.143']]
        self.find_net_by_name('public')["gateway"] = '192.18.17.1'
        self.find_net_by_name('public')["netmask"] = '255.255.255.0'
        self.find_net_by_name('management')["cidr"] = '192.18.17.0/25'

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            "Address space intersection between networks:\n",
            task['message'])
        self.assertIn("public", task['message'])
        self.assertIn("management", task['message'])

    def test_network_checking_no_public_floating_ranges_intersection(self):
        self.find_net_by_name('public')["ip_ranges"] = \
            [['192.18.17.5', '192.18.17.43'],
             ['192.18.17.59', '192.18.17.90']]
        self.find_net_by_name('floating')["ip_ranges"] = \
            [['192.18.17.125', '192.18.17.143'],
             ['192.18.17.159', '192.18.17.190']]
        self.find_net_by_name('public')["gateway"] = '192.18.17.1'
        self.find_net_by_name('public')["netmask"] = '255.255.255.0'

        self.update_nova_networks_success(self.cluster.id, self.nets)

    def test_network_checking_fails_if_public_ranges_intersection(self):
        self.find_net_by_name('public')["ip_ranges"] = \
            [['192.18.17.65', '192.18.17.143'],
             ['192.18.17.129', '192.18.17.190']]
        self.find_net_by_name('public')["gateway"] = '192.18.17.1'

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Address space intersection between ranges of public network."
        )

    def test_network_checking_fails_if_public_gateway_not_in_cidr(self):
        self.find_net_by_name('public')["ip_ranges"] = \
            [['192.18.17.5', '192.18.17.43'],
             ['192.18.17.59', '192.18.17.90']]
        self.find_net_by_name('public')["gateway"] = '192.18.18.1'
        self.find_net_by_name('public')["netmask"] = '255.255.255.0'

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Public gateway and public ranges are not in one CIDR."
        )

    def test_network_checking_fails_if_public_gateway_range_intersection(self):
        self.find_net_by_name('public')["ip_ranges"] = \
            [['192.18.17.5', '192.18.17.43'],
             ['192.18.17.59', '192.18.17.90']]
        self.find_net_by_name('public')["gateway"] = '192.18.17.77'
        self.find_net_by_name('public')["netmask"] = '255.255.255.0'

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Address intersection between public gateway and IP range of "
            "public network."
        )

        self.find_net_by_name('public')["ip_ranges"] = \
            [['192.18.17.5', '192.18.17.99']]
        self.find_net_by_name('public')["gateway"] = '192.18.17.55'

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Address intersection between public gateway and IP range of "
            "public network."
        )

    def test_network_checking_fails_if_floating_ranges_intersection(self):
        self.find_net_by_name('floating')["ip_ranges"] = \
            [['192.18.17.65', '192.18.17.143'],
             ['192.18.17.129', '192.18.17.190']]

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Address space intersection between ranges of floating network."
        )

    def test_network_checking_fails_if_amount_flatdhcp(self):
        net = self.find_net_by_name('fixed')
        net["amount"] = 2
        net["cidr"] = "10.10.0.0/23"

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Network amount for 'fixed' is more than 1 "
            "while using FlatDHCP manager."
        )

    def test_network_checking_fails_if_vlan_ids_intersection(self):
        self.find_net_by_name('public')["vlan_start"] = 111
        self.find_net_by_name('management')["vlan_start"] = 111

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            " networks use the same VLAN ID(s). "
            "You should assign different VLAN IDs to every network.",
            task['message'])
        self.assertIn("management", task['message'])
        self.assertIn("public", task['message'])

    def test_network_checking_fails_if_vlan_id_in_fixed_vlan_range(self):
        self.nets['net_manager'] = 'VLANManager'
        self.find_net_by_name('public')["vlan_start"] = 1111
        self.find_net_by_name('fixed')["vlan_start"] = 1100
        self.find_net_by_name('fixed')["amount"] = 20

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            " networks use the same VLAN ID(s). "
            "You should assign different VLAN IDs to every network.",
            task['message'])
        self.assertIn("fixed", task['message'])
        self.assertIn("public", task['message'])

    def test_network_checking_fails_if_vlan_id_not_in_allowed_range(self):
        self.find_net_by_name('public')["vlan_start"] = 5555

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "VLAN ID(s) is out of range for public network."
        )

    def test_network_checking_fails_if_public_floating_vlan_not_equal(self):
        self.find_net_by_name('public')["vlan_start"] = 111
        self.find_net_by_name('floating')["vlan_start"] = 112

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            " networks don't use the same VLAN ID(s). "
            "These networks must use the same VLAN ID(s).",
            task['message']
        )
        self.assertIn("floating", task['message'])
        self.assertIn("public", task['message'])

    def test_network_checking_fails_if_public_floating_not_on_one_nic(self):
        self.find_net_by_name('public')["vlan_start"] = 111
        self.find_net_by_name('floating')["vlan_start"] = 111
        self.update_nova_networks_success(self.cluster.id, self.nets)

        node_db = self.env.nodes[0]
        resp = self.app.get(reverse('NodeNICsHandler',
                                    kwargs={'node_id': node_db.id}),
                            headers=self.default_headers)
        nics = json.loads(resp.body)

        for nic in nics:
            for net in nic['assigned_networks']:
                if net['name'] == 'fuelweb_admin':
                    admin_nic = nic
                else:
                    other_nic = nic
                    if net['name'] == 'public':
                        public = net
        other_nic['assigned_networks'].remove(public)
        admin_nic['assigned_networks'].append(public)

        resp = self.app.put(reverse('NodeNICsHandler',
                                    kwargs={'node_id': node_db.id}),
                            json.dumps(nics),
                            headers=self.default_headers)
        self.assertEquals(resp.status, 200)

        task = self.set_cluster_changes_w_error(self.cluster.id)
        self.assertIn(
            "Public and floating networks are not assigned to the "
            "same physical interface. These networks must be assigned "
            "to the same physical interface. Affected nodes:\nUntitled",
            task['message']
        )

    def test_network_size_and_amount_not_fit_cidr(self):
        net = self.find_net_by_name('fixed')
        net["amount"] = 1
        net["cidr"] = "10.10.0.0/24"
        net["network_size"] = "128"
        self.update_nova_networks_success(self.cluster.id, self.nets)

        net["network_size"] = "512"
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Number of fixed networks (1) doesn't fit into "
            "fixed CIDR (10.10.0.0/24) and size of one fixed network (512)."
        )

        self.nets['net_manager'] = 'VlanManager'
        net["amount"] = 8
        net["network_size"] = "32"
        self.update_nova_networks_success(self.cluster.id, self.nets)

        net["amount"] = 32
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Number of fixed networks (32) doesn't fit into "
            "fixed CIDR (10.10.0.0/24) and size of one fixed network (32)."
        )

    def test_network_fit_abc_classes_exclude_loopback(self):
        self.find_net_by_name('management')['cidr'] = '127.19.216.0/24'
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "management network address space is inside loopback range "
            "(127.0.0.0/8). It must have no intersection with "
            "loopback range."
        )

        self.find_net_by_name('management')['cidr'] = '227.19.216.0/24'
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "management network address space does not belong to "
            "A, B, C network classes. It must belong to either "
            "A, B or C network class."
        )

    def test_network_gw_and_ranges_intersect_w_subnet_or_broadcast(self):
        self.find_net_by_name('public')['gateway'] = '172.16.0.0'
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "public network gateway address is equal to either subnet address "
            "or broadcast address of the network."
        )

        self.find_net_by_name('public')['gateway'] = '172.16.0.255'
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "public network gateway address is equal to either subnet address "
            "or broadcast address of the network."
        )

        self.find_net_by_name('public')['gateway'] = '172.16.0.125'
        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.0',
                                                         '172.16.0.122']]
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "public network IP range [172.16.0.0-172.16.0.122] intersect "
            "with either subnet address or broadcast address of the network."
        )

        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.255',
                                                         '172.16.0.255']]
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "public network IP range [172.16.0.255-172.16.0.255] intersect "
            "with either subnet address or broadcast address of the network."
        )

        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.2',
                                                         '172.16.0.122']]
        self.find_net_by_name('fixed')['gateway'] = '10.0.0.0'
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "fixed network gateway address is equal to either subnet address "
            "or broadcast address of the network."
        )

        self.find_net_by_name('fixed')['gateway'] = '10.0.255.255'
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "fixed network gateway address is equal to either subnet address "
            "or broadcast address of the network."
        )


class TestNeutronHandlersGre(TestNetworkChecking):

    def setUp(self):
        super(TestNeutronHandlersGre, self).setUp()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {"name": "eth0", "mac": "00:00:00:00:00:66"},
            {"name": "eth1", "mac": "00:00:00:00:00:77"}])
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True,
                 'meta': meta}
            ]
        )
        self.cluster = self.env.clusters[0]
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.nets = json.loads(resp.body)

    def test_network_checking(self):
        self.update_neutron_networks_success(self.cluster.id, self.nets)

        ngs_created = self.db.query(NetworkGroup).filter(
            NetworkGroup.name.in_([n['name'] for n in self.nets['networks']])
        ).all()
        self.assertEquals(len(ngs_created), len(self.nets['networks']))

    # TODO(adanin) Provide a positive test that it's allowed to move any
    #      network to the Admin interface.

    def test_network_checking_fails_if_admin_intersection(self):
        admin_ng = self.env.network_manager.get_admin_network_group()
        self.find_net_by_name('storage')["cidr"] = admin_ng.cidr

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            "Address space intersection between networks:\n",
            task['message'])
        self.assertIn("admin (PXE)", task['message'])
        self.assertIn("storage", task['message'])

    def test_network_checking_fails_if_untagged_intersection(self):
        for n in self.nets['networks']:
            n['vlan_start'] = None

        self.env.neutron_networks_put(self.cluster.id, self.nets)

        task = self.set_cluster_changes_w_error(self.cluster.id)
        self.assertEquals(
            task['message'].find(
                "Some untagged networks are "
                "assigned to the same physical interface. "
                "You should assign them to "
                "different physical interfaces:"),
            0
        )

    def test_network_checking_fails_if_public_gateway_not_in_cidr(self):
        self.find_net_by_name('public')['gateway'] = '172.16.10.1'
        virt_nets = self.nets['neutron_parameters']['predefined_networks']
        virt_nets['net04_ext']['L3']['floating'] = ['172.16.10.130',
                                                    '172.16.10.254']

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Public gateway and public ranges are not in one CIDR."
        )

    def test_network_checking_fails_if_public_gateway_range_intersection(self):
        self.find_net_by_name('public')["ip_ranges"] = \
            [['172.16.0.5', '172.16.0.43'],
             ['172.16.0.59', '172.16.0.90']]
        self.find_net_by_name('public')["gateway"] = '172.16.0.77'
        self.find_net_by_name('public')["netmask"] = '255.255.255.0'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Address intersection between public gateway and IP range of "
            "public network."
        )

        self.find_net_by_name('public')["ip_ranges"] = \
            [['172.16.0.5', '172.16.0.99']]
        self.find_net_by_name('public')["gateway"] = '172.16.0.55'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Address intersection between public gateway and IP range of "
            "public network."
        )

    def test_network_checking_fails_if_public_float_range_not_in_cidr(self):
        self.find_net_by_name('public')['cidr'] = '172.16.10.0/24'
        self.find_net_by_name('public')['gateway'] = '172.16.10.1'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Floating address range 172.16.0.130:172.16.0.254 is not in "
            "public address space 172.16.10.0/24."
        )

    def test_network_checking_fails_if_network_ranges_intersect(self):
        self.find_net_by_name('management')['cidr'] = \
            self.find_net_by_name('storage')['cidr']

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            "Address space intersection between networks:\n",
            task['message'])
        self.assertIn("management", task['message'])
        self.assertIn("storage", task['message'])

    def test_network_checking_fails_if_public_gw_ranges_intersect(self):
        self.find_net_by_name('public')['gateway'] = '172.16.0.11'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Address intersection between public gateway "
            "and IP range of public network."
        )

    def test_network_checking_fails_if_public_ranges_intersect(self):
        self.find_net_by_name('public')['ip_ranges'] = \
            [['172.16.0.2', '172.16.0.77'],
             ['172.16.0.55', '172.16.0.121']]

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Address space intersection between ranges "
            "of public network."
        )

    def test_network_checking_fails_if_public_float_ranges_intersect(self):
        self.find_net_by_name('public')['ip_ranges'] = \
            [['172.16.0.2', '172.16.0.33'],
             ['172.16.0.55', '172.16.0.222']]

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Address space intersection between ranges "
            "of public and external network."
        )

    def test_network_checking_fails_if_network_cidr_too_small(self):
        self.find_net_by_name('management')['cidr'] = '192.168.0.0/25'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "CIDR size for network 'management' "
            "is less than required"
        )

    def test_network_checking_public_network_cidr_became_smaller(self):
        self.assertEquals(self.find_net_by_name('public')['network_size'], 256)

        self.find_net_by_name('public')['netmask'] = '255.255.255.128'
        self.find_net_by_name('public')['gateway'] = '172.16.0.1'
        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.2',
                                                         '172.16.0.77']]
        virt_nets = self.nets['neutron_parameters']['predefined_networks']
        virt_nets['net04_ext']['L3']['floating'] = ['172.16.0.99',
                                                    '172.16.0.111']

        self.update_neutron_networks_success(self.cluster.id, self.nets)
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.nets = json.loads(resp.body)
        self.assertEquals(self.find_net_by_name('public')['cidr'],
                          '172.16.0.0/25')
        self.assertEquals(self.find_net_by_name('public')['network_size'], 128)

    def test_network_checking_fails_on_network_vlan_match(self):
        self.find_net_by_name('management')['vlan_start'] = '111'
        self.find_net_by_name('storage')['vlan_start'] = '111'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            " networks use the same VLAN tags. "
            "You should assign different VLAN tag "
            "to every network.",
            task['message'])
        self.assertIn("management", task['message'])
        self.assertIn("storage", task['message'])

    def test_network_checking_fails_if_internal_gateway_not_in_cidr(self):
        int = self.nets['neutron_parameters']['predefined_networks']['net04']
        int['L3']['gateway'] = '172.16.10.1'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Internal gateway 172.16.10.1 is not in "
            "internal address space 192.168.111.0/24."
        )

    def test_network_checking_fails_if_internal_w_floating_intersection(self):
        int = self.nets['neutron_parameters']['predefined_networks']['net04']
        int['L3']['cidr'] = '172.16.0.128/26'
        int['L3']['gateway'] = '172.16.0.129'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Intersection between internal CIDR and floating range."
        )

    def test_network_fit_abc_classes_exclude_loopback(self):
        self.find_net_by_name('management')['cidr'] = '127.19.216.0/24'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "management network address space is inside loopback range "
            "(127.0.0.0/8). It must have no intersection with "
            "loopback range."
        )

        self.find_net_by_name('management')['cidr'] = '227.19.216.0/24'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "management network address space does not belong to "
            "A, B, C network classes. It must belong to either "
            "A, B or C network class."
        )

    def test_network_gw_and_ranges_intersect_w_subnet_or_broadcast(self):
        self.find_net_by_name('public')['gateway'] = '172.16.0.0'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "public network gateway address is equal to either subnet address "
            "or broadcast address of the network."
        )

        self.find_net_by_name('public')['gateway'] = '172.16.0.255'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "public network gateway address is equal to either subnet address "
            "or broadcast address of the network."
        )

        self.find_net_by_name('public')['gateway'] = '172.16.0.125'
        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.0',
                                                         '172.16.0.122']]
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "public network IP range [172.16.0.0-172.16.0.122] intersect "
            "with either subnet address or broadcast address of the network."
        )

        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.255',
                                                         '172.16.0.255']]
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "public network IP range [172.16.0.255-172.16.0.255] intersect "
            "with either subnet address or broadcast address of the network."
        )

        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.55',
                                                         '172.16.0.99']]
        virt_nets = self.nets['neutron_parameters']['predefined_networks']
        virt_nets['net04_ext']['L3']['floating'] = ['172.16.0.0',
                                                    '172.16.0.33']
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Neutron L3 external floating range [172.16.0.0-172.16.0.33] "
            "intersect with either subnet address or broadcast address "
            "of public network."
        )

        virt_nets['net04_ext']['L3']['floating'] = ['172.16.0.155',
                                                    '172.16.0.255']
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Neutron L3 external floating range [172.16.0.155-172.16.0.255] "
            "intersect with either subnet address or broadcast address "
            "of public network."
        )

        virt_nets['net04_ext']['L3']['floating'] = ['172.16.0.155',
                                                    '172.16.0.199']
        virt_nets['net04']['L3']['cidr'] = '192.168.111.0/24'
        virt_nets['net04']['L3']['gateway'] = '192.168.111.0'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Neutron L3 internal network gateway address is equal to "
            "either subnet address or broadcast address of the network."
        )

        virt_nets['net04']['L3']['gateway'] = '192.168.111.255'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "Neutron L3 internal network gateway address is equal to "
            "either subnet address or broadcast address of the network."
        )


class TestNeutronHandlersVlan(TestNetworkChecking):

    def setUp(self):
        super(TestNeutronHandlersVlan, self).setUp()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {"name": "eth0", "mac": "00:00:00:00:00:66"},
            {"name": "eth1", "mac": "00:00:00:00:00:77"}])
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'vlan'
            },
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True,
                 'meta': meta}
            ]
        )
        self.cluster = self.env.clusters[0]
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.nets = json.loads(resp.body)

    def test_network_checking(self):
        self.update_neutron_networks_success(self.cluster.id, self.nets)

        ngs_created = self.db.query(NetworkGroup).filter(
            NetworkGroup.name.in_([n['name'] for n in self.nets['networks']])
        ).all()
        self.assertEquals(len(ngs_created), len(self.nets['networks']))

    def test_network_checking_failed_if_networks_tags_in_neutron_range(self):
        self.find_net_by_name('storage')['vlan_start'] = 1000

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEquals(
            task['message'],
            "VLAN tags of storage network(s) intersect with "
            "VLAN ID range defined for Neutron L2. "
            "Networks VLAN tags must not intersect "
            "with Neutron L2 VLAN ID range.")
