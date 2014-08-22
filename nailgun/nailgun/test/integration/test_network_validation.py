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

from netaddr import IPAddress
from netaddr import IPNetwork

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import NeutronConfig
from nailgun.db.sqlalchemy.models import NovaNetworkConfig
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest


class TestNetworkChecking(BaseIntegrationTest):

    def find_net_by_name(self, name):
        for net in self.nets['networks']:
            if net['name'] == name:
                return net

    def check_result_format(self, task, cluster_id):
        if task.get('result'):
            result = task['result']
            self.assertIsInstance(result, list)
            ng_fields = \
                NetworkGroup.__mapper__.columns.keys() + ["ip_ranges"]
            cluster_db = self.db.query(Cluster).get(cluster_id)
            ng_fields += NeutronConfig.__mapper__.columns.keys() \
                if cluster_db.net_provider == 'neutron' else \
                NovaNetworkConfig.__mapper__.columns.keys()
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
        self.assertEqual(resp.status_code, 202)
        task = jsonutils.loads(resp.body)
        self.assertEqual(task['status'], 'error')
        self.assertEqual(task['progress'], 100)
        self.assertEqual(task['name'], 'deploy')
        self.check_result_format(task, cluster_id)
        return task

    def update_nova_networks_w_error(self, cluster_id, nets):
        resp = self.env.nova_networks_put(cluster_id, nets,
                                          expect_errors=True)
        self.assertEqual(resp.status_code, 202)
        task = jsonutils.loads(resp.body)
        self.assertEqual(task['status'], 'error')
        self.assertEqual(task['progress'], 100)
        self.assertEqual(task['name'], 'check_networks')
        self.check_result_format(task, cluster_id)
        return task

    def update_nova_networks_success(self, cluster_id, nets):
        resp = self.env.nova_networks_put(cluster_id, nets)
        self.assertEqual(resp.status_code, 202)
        task = jsonutils.loads(resp.body)
        self.assertEqual(task['status'], 'ready')
        self.assertEqual(task['progress'], 100)
        self.assertEqual(task['name'], 'check_networks')
        return task

    def update_neutron_networks_w_error(self, cluster_id, nets):
        resp = self.env.neutron_networks_put(cluster_id, nets,
                                             expect_errors=True)
        self.assertEqual(resp.status_code, 202)
        task = jsonutils.loads(resp.body)
        self.assertEqual(task['status'], 'error')
        self.assertEqual(task['progress'], 100)
        self.assertEqual(task['name'], 'check_networks')
        self.check_result_format(task, cluster_id)
        return task

    def update_neutron_networks_success(self, cluster_id, nets):
        resp = self.env.neutron_networks_put(cluster_id, nets)
        self.assertEqual(resp.status_code, 202)
        task = jsonutils.loads(resp.body)
        self.assertEqual(task['status'], 'ready')
        self.assertEqual(task['progress'], 100)
        self.assertEqual(task['name'], 'check_networks')
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
        self.nets = jsonutils.loads(resp.body)

    def test_network_checking(self):
        self.update_nova_networks_success(self.cluster.id, self.nets)

        ngs_created = self.db.query(NetworkGroup).filter(
            NetworkGroup.name.in_([n['name'] for n in self.nets['networks']])
        ).all()
        self.assertEqual(len(ngs_created), len(self.nets['networks']))

    def test_network_checking_fails_if_admin_intersection(self):
        admin_ng = self.env.network_manager.get_admin_network_group()
        self.nets['networking_parameters']["fixed_networks_cidr"] = \
            admin_ng.cidr

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertIn(
            "Address space intersection between networks:\n",
            task['message'])
        self.assertIn("admin (PXE)", task['message'])
        self.assertIn("fixed", task['message'])

    def test_network_checking_fails_if_admin_intersection_ip_range(self):
        admin_ng = self.env.network_manager.get_admin_network_group()
        cidr = IPNetwork(admin_ng.cidr)
        flt_r0 = str(IPAddress(cidr.first + 2))
        flt_r1 = str(IPAddress(cidr.last))
        self.nets['networking_parameters']['floating_ranges'] = \
            [[flt_r0, flt_r1]]

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            "Address space intersection between floating range '{0}-{1}' and "
            "'admin (PXE)' network.".format(flt_r0, flt_r1),
            task['message'])

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
        self.find_net_by_name('public')["cidr"] = '192.18.17.0/24'
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
        self.nets['networking_parameters']["floating_ranges"] = \
            [['192.18.17.125', '192.18.17.143'],
             ['192.18.17.159', '192.18.17.190']]
        self.find_net_by_name('public')["gateway"] = '192.18.17.1'
        self.find_net_by_name('public')["cidr"] = '192.18.17.0/24'

        self.update_nova_networks_success(self.cluster.id, self.nets)

    def test_network_checking_fails_if_public_ranges_intersection(self):
        self.find_net_by_name('public')["ip_ranges"] = \
            [['192.18.17.65', '192.18.17.123'],
             ['192.18.17.99', '192.18.17.129']]
        self.find_net_by_name('public')["gateway"] = '192.18.17.1'
        self.find_net_by_name('public')["cidr"] = '192.18.17.0/24'

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Address space intersection between ranges of public network."
        )

    def test_network_checking_fails_if_public_gateway_not_in_cidr(self):
        self.find_net_by_name('public')["ip_ranges"] = \
            [['192.18.17.5', '192.18.17.43'],
             ['192.18.17.59', '192.18.17.90']]
        self.find_net_by_name('public')["gateway"] = '192.18.18.1'
        self.find_net_by_name('public')["cidr"] = '192.18.18.0/24'

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Public gateway and public ranges are not in one CIDR."
        )

    def test_network_checking_fails_if_public_gateway_range_intersection(self):
        self.find_net_by_name('public')["ip_ranges"] = \
            [['192.18.17.5', '192.18.17.43'],
             ['192.18.17.59', '192.18.17.90']]
        self.find_net_by_name('public')["gateway"] = '192.18.17.77'
        self.find_net_by_name('public')["cidr"] = '192.18.17.0/24'

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Address intersection between public gateway and IP range of "
            "public network."
        )

        self.find_net_by_name('public')["ip_ranges"] = \
            [['192.18.17.5', '192.18.17.99']]
        self.find_net_by_name('public')["gateway"] = '192.18.17.55'

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Address intersection between public gateway and IP range of "
            "public network."
        )

    def test_network_checking_fails_if_floating_ranges_intersection(self):
        self.nets['networking_parameters']["floating_ranges"] = \
            [['192.18.17.129', '192.18.17.143'],
             ['192.18.17.133', '192.18.17.190']]

        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Address space intersection between ranges of floating network."
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
        self.nets['networking_parameters']['net_manager'] = 'VLANManager'
        self.find_net_by_name('public')["vlan_start"] = 1111
        self.nets['networking_parameters']['fixed_networks_vlan_start'] = \
            1100
        self.nets['networking_parameters']['fixed_networks_amount'] = 20

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
        self.assertEqual(
            task['message'],
            "VLAN ID(s) is out of range for public network."
        )

    def test_network_size_not_fit_cidr_in_flatdhcp(self):
        self.nets['networking_parameters']['net_manager'] = 'FlatDHCPManager'
        self.nets['networking_parameters']['fixed_networks_cidr'] = \
            "10.10.0.0/28"
        self.nets['networking_parameters']['fixed_networks_amount'] = 1
        self.nets['networking_parameters']['fixed_network_size'] = \
            "256"
        task = self.update_nova_networks_success(self.cluster.id, self.nets)

        self.assertEqual(task['status'], 'ready')

    def test_network_size_and_amount_not_fit_cidr(self):
        self.nets['networking_parameters']['net_manager'] = 'VlanManager'
        self.nets['networking_parameters']['fixed_networks_cidr'] = \
            "10.10.0.0/24"
        self.nets['networking_parameters']['fixed_networks_amount'] = 8
        self.nets['networking_parameters']['fixed_network_size'] = \
            "32"
        self.update_nova_networks_success(self.cluster.id, self.nets)

        self.nets['networking_parameters']['fixed_networks_amount'] = 32
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Number of fixed networks (32) doesn't fit into "
            "fixed CIDR (10.10.0.0/24) and size of one fixed network (32)."
        )

    def test_network_fit_abc_classes_exclude_loopback(self):
        self.find_net_by_name('management')['cidr'] = '127.19.216.0/24'
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "management network address space is inside loopback range "
            "(127.0.0.0/8). It must have no intersection with "
            "loopback range."
        )

        self.find_net_by_name('management')['cidr'] = '227.19.216.0/24'
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "management network address space does not belong to "
            "A, B, C network classes. It must belong to either "
            "A, B or C network class."
        )

    def test_network_gw_and_ranges_intersect_w_subnet_or_broadcast(self):
        self.find_net_by_name('public')['gateway'] = '172.16.0.0'
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "public network gateway address is equal to either subnet address "
            "or broadcast address of the network."
        )

        self.find_net_by_name('public')['gateway'] = '172.16.0.255'
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "public network gateway address is equal to either subnet address "
            "or broadcast address of the network."
        )

        self.find_net_by_name('public')['gateway'] = '172.16.0.125'
        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.0',
                                                         '172.16.0.122']]
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "public network IP range [172.16.0.0-172.16.0.122] intersect "
            "with either subnet address or broadcast address of the network."
        )

        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.255',
                                                         '172.16.0.255']]
        task = self.update_nova_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "public network IP range [172.16.0.255-172.16.0.255] intersect "
            "with either subnet address or broadcast address of the network."
        )

        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.2',
                                                         '172.16.0.122']]
        self.update_nova_networks_success(self.cluster.id, self.nets)


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
        self.nets = jsonutils.loads(resp.body)

    def test_network_checking(self):
        self.update_neutron_networks_success(self.cluster.id, self.nets)

        ngs_created = self.db.query(NetworkGroup).filter(
            NetworkGroup.name.in_([n['name'] for n in self.nets['networks']])
        ).all()
        self.assertEqual(len(ngs_created), len(self.nets['networks']))

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

        self.update_neutron_networks_success(self.cluster.id, self.nets)

        task = self.set_cluster_changes_w_error(self.cluster.id)
        self.assertIn(
            "Some untagged networks are "
            "assigned to the same physical interface. "
            "You should assign them to "
            "different physical interfaces. Affected:\n",
            task['message']
        )
        self.assertIn("admin (PXE)", task['message'])
        self.assertIn("storage", task['message'])
        self.assertIn("management", task['message'])

    def test_network_checking_fails_if_public_gateway_not_in_cidr(self):
        self.find_net_by_name('public')['cidr'] = '172.16.10.0/24'
        self.find_net_by_name('public')['gateway'] = '172.16.10.1'
        self.nets['networking_parameters']['floating_ranges'] = \
            [['172.16.10.130', '172.16.10.254']]

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Public gateway and public ranges are not in one CIDR."
        )

    def test_network_checking_fails_if_public_gateway_range_intersection(self):
        self.find_net_by_name('public')["ip_ranges"] = \
            [['172.16.0.5', '172.16.0.43'],
             ['172.16.0.59', '172.16.0.90']]
        self.find_net_by_name('public')["gateway"] = '172.16.0.77'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Address intersection between public gateway and IP range of "
            "public network."
        )

        self.find_net_by_name('public')["ip_ranges"] = \
            [['172.16.0.5', '172.16.0.99']]
        self.find_net_by_name('public')["gateway"] = '172.16.0.55'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Address intersection between public gateway and IP range of "
            "public network."
        )

    def test_network_checking_fails_if_public_float_range_not_in_cidr(self):
        self.find_net_by_name('public')['cidr'] = '172.16.10.0/24'
        self.find_net_by_name('public')['gateway'] = '172.16.10.1'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
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
        self.assertEqual(
            task['message'],
            "Address intersection between public gateway "
            "and IP range of public network."
        )

    def test_network_checking_fails_if_public_ranges_intersect(self):
        self.find_net_by_name('public')['ip_ranges'] = \
            [['172.16.0.2', '172.16.0.77'],
             ['172.16.0.55', '172.16.0.121']]

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Address space intersection between ranges "
            "of public network."
        )

    def test_network_checking_fails_if_public_float_ranges_intersect(self):
        self.find_net_by_name('public')['ip_ranges'] = \
            [['172.16.0.2', '172.16.0.33'],
             ['172.16.0.55', '172.16.0.222']]

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Address space intersection between ranges "
            "of public and external network."
        )

    def test_network_checking_public_network_cidr_became_smaller(self):
        self.find_net_by_name('public')['cidr'] = '172.16.0.0/25'
        self.find_net_by_name('public')['gateway'] = '172.16.0.1'
        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.2',
                                                         '172.16.0.77']]
        self.nets['networking_parameters']['floating_ranges'] = \
            [['172.16.0.99', '172.16.0.111']]

        self.update_neutron_networks_success(self.cluster.id, self.nets)
        resp = self.env.neutron_networks_get(self.cluster.id)
        self.nets = jsonutils.loads(resp.body)
        self.assertEqual(self.find_net_by_name('public')['cidr'],
                         '172.16.0.0/25')

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
        self.nets['networking_parameters']['internal_gateway'] = '172.16.10.1'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Internal gateway 172.16.10.1 is not in "
            "internal address space 192.168.111.0/24."
        )

    def test_network_checking_fails_if_internal_w_floating_intersection(self):
        self.nets['networking_parameters']['internal_cidr'] = '172.16.0.128/26'
        self.nets['networking_parameters']['internal_gateway'] = '172.16.0.129'

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Intersection between internal CIDR and floating range."
        )

    def test_network_fit_abc_classes_exclude_loopback(self):
        self.find_net_by_name('management')['cidr'] = '127.19.216.0/24'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "management network address space is inside loopback range "
            "(127.0.0.0/8). It must have no intersection with "
            "loopback range."
        )

        self.find_net_by_name('management')['cidr'] = '227.19.216.0/24'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "management network address space does not belong to "
            "A, B, C network classes. It must belong to either "
            "A, B or C network class."
        )

    def test_network_gw_and_ranges_intersect_w_subnet_or_broadcast(self):
        self.find_net_by_name('public')['gateway'] = '172.16.0.0'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "public network gateway address is equal to either subnet address "
            "or broadcast address of the network."
        )

        self.find_net_by_name('public')['gateway'] = '172.16.0.255'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "public network gateway address is equal to either subnet address "
            "or broadcast address of the network."
        )

        self.find_net_by_name('public')['gateway'] = '172.16.0.125'
        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.0',
                                                         '172.16.0.122']]
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "public network IP range [172.16.0.0-172.16.0.122] intersect "
            "with either subnet address or broadcast address of the network."
        )

        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.255',
                                                         '172.16.0.255']]
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "public network IP range [172.16.0.255-172.16.0.255] intersect "
            "with either subnet address or broadcast address of the network."
        )

        self.find_net_by_name('public')['ip_ranges'] = [['172.16.0.55',
                                                         '172.16.0.99']]
        self.nets['networking_parameters']['floating_ranges'] = \
            [['172.16.0.0', '172.16.0.33']]
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Neutron L3 external floating range [172.16.0.0-172.16.0.33] "
            "intersect with either subnet address or broadcast address "
            "of public network."
        )

        self.nets['networking_parameters']['floating_ranges'] = \
            [['172.16.0.155', '172.16.0.255']]
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Neutron L3 external floating range [172.16.0.155-172.16.0.255] "
            "intersect with either subnet address or broadcast address "
            "of public network."
        )

        self.nets['networking_parameters']['floating_ranges'] = \
            [['172.16.0.155', '172.16.0.199']]
        self.nets['networking_parameters']['internal_cidr'] = \
            '192.168.111.0/24'
        self.nets['networking_parameters']['internal_gateway'] = \
            '192.168.111.0'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "Neutron L3 internal network gateway address is equal to "
            "either subnet address or broadcast address of the network."
        )

        self.nets['networking_parameters']['internal_gateway'] = \
            '192.168.111.255'
        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
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
        self.nets = jsonutils.loads(resp.body)

    def test_network_checking(self):
        self.update_neutron_networks_success(self.cluster.id, self.nets)

        ngs_created = self.db.query(NetworkGroup).filter(
            NetworkGroup.name.in_([n['name'] for n in self.nets['networks']])
        ).all()
        self.assertEqual(len(ngs_created), len(self.nets['networks']))

    def test_network_checking_failed_if_networks_tags_in_neutron_range(self):
        self.find_net_by_name('storage')['vlan_start'] = 1000

        task = self.update_neutron_networks_w_error(self.cluster.id, self.nets)
        self.assertEqual(
            task['message'],
            "VLAN tags of storage network(s) intersect with "
            "VLAN ID range defined for Neutron L2. "
            "Networks VLAN tags must not intersect "
            "with Neutron L2 VLAN ID range.")
