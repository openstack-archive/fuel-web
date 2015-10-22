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

import copy
from mock import MagicMock
from mock import patch

from nailgun import consts
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import node
from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.network.checker import NetworkCheck
from nailgun.task import helpers
from nailgun.task.manager import ApplyChangesTaskManager
from nailgun.test.base import BaseIntegrationTest


class FakeTask(object):
    def __init__(self, cluster):
        self.cluster = cluster


class TestNetworkCheck(BaseIntegrationTest):

    def setUp(self):
        super(TestNetworkCheck, self).setUp()
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": True,
                 "pending_addition": True},
            ]
        )
        self.task = FakeTask(self.env.clusters[0])

    @patch.object(helpers, 'db')
    def test_check_untagged_intersection_failed(self, mocked_db):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}
            ]
        )
        cluster_db = self.db.query(Cluster).get(cluster['id'])

        ng1 = NetworkGroup()
        ng1.name = consts.NETWORKS.storage
        ng2 = NetworkGroup()
        ng2.name = consts.NETWORKS.management
        self.env.db().add_all([ng1, ng2])
        self.env.db().flush()

        checker = NetworkCheck(FakeTask(cluster_db), {})
        checker.networks = [{'id': ng1.id,
                             'cidr': '192.168.0.0/24',
                             'name': ng1.name,
                             'vlan_start': None,
                             'meta': {'notation': consts.NETWORK_NOTATION.cidr}
                             },
                            {'id': ng2.id,
                             'cidr': '192.168.0.0/26',
                             'name': ng2.name,
                             'vlan_start': None,
                             'meta': {'notation': consts.NETWORK_NOTATION.cidr}
                             }]
        checker.cluster.nodes[0].interfaces[0].assigned_networks_list = \
            [ng1, ng2]
        checker.cluster.nodes[0].interfaces[1].assigned_networks_list = \
            [ng1, ng2]
        self.env.db.flush()
        self.assertRaises(errors.NetworkCheckError,
                          checker.check_untagged_intersection)

    def test_check_untagged_intersection(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}
            ]
        )
        cluster_db = self.db.query(Cluster).get(cluster['id'])
        checker = NetworkCheck(FakeTask(cluster_db), {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'name': 'fake1',
                             'vlan_start': None,
                             'meta': {'notation': 'cidr'}}]
        ng1 = NetworkGroup()
        ng1.name = 'fake3'
        ng1.id = 3
        ng2 = NetworkGroup()
        ng2.name = 'fake4'
        ng2.id = 4
        checker.cluster.nodes[0].interfaces[0].assigned_networks_list = \
            [ng1, ng2]

        self.assertNotRaises(errors.NetworkCheckError,
                             checker.check_untagged_intersection)

    @patch.object(helpers, 'db')
    def test_check_network_address_spaces_intersection(self, _):
        cluster = self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network},
            nodes_kwargs=[
                {"api": True,
                 "pending_addition": True},
            ]
        )
        self.task = FakeTask(self.db.query(Cluster).get(cluster['id']))

        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'name': 'fake1',
                             'meta': {'notation': 'cidr'}},
                            {'id': 2,
                             'cidr': '192.168.0.0/26',
                             'name': 'fake2',
                             'meta': {'notation': 'cidr'}}]

        self.assertRaises(errors.NetworkCheckError,
                          checker.check_network_address_spaces_intersection)

        checker = NetworkCheck(self.task, {})

        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'name': 'fake1',
                             'meta': {'notation': 'cidr'}},
                            {'id': 2,
                             'cidr': '192.168.1.0/26',
                             'name': 'fake2',
                             'meta': {'notation': 'cidr'}}]
        checker.network_config['fixed_networks_cidr'] = '10.20.0.0/24'
        self.assertNotRaises(errors.NetworkCheckError,
                             checker.check_network_address_spaces_intersection)

        checker = NetworkCheck(self.task, {})

        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'name': 'fake1',
                             'meta': {'notation': 'cidr'}},
                            {'id': 2,
                             'cidr': '10.20.0.0/26',
                             'name': 'fake2',
                             'meta': {'notation': 'cidr'}}]
        checker.network_config['fixed_networks_cidr'] = '10.20.0.0/24'
        self.assertRaises(errors.NetworkCheckError,
                          checker.check_network_address_spaces_intersection)

    @patch.object(helpers, 'db')
    def test_check_public_floating_ranges_intersection(self, _):
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'name': 'public',
                             'gateway': '192.168.0.1',
                             'ip_ranges': ['192.168.0.1', '192.168.0.100'],
                             'meta': {'notation': 'cidr'}}]
        checker.network_config['floating_ranges'] = ['192.168.0.100',
                                                     '192.168.0.199']
        self.assertRaises(errors.NetworkCheckError,
                          checker.check_public_floating_ranges_intersection)

        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'name': 'public',
                             'gateway': '192.168.0.1',
                             'ip_ranges': [('192.168.0.1', '192.168.0.254')],
                             'meta': {'notation': 'cidr'}}]
        checker.network_config['floating_ranges'] = ['192.168.2.0/24']
        self.assertRaises(errors.NetworkCheckError,
                          checker.check_public_floating_ranges_intersection)
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'name': 'public',
                             'gateway': '192.168.0.1',
                             'ip_ranges': [('192.168.0.2', '192.168.0.254')],
                             'meta': {'notation': 'cidr'}}]
        checker.network_config['floating_ranges'] = ['192.168.2.0/24']

        self.assertNotRaises(errors.NetworkCheckError,
                             checker.check_public_floating_ranges_intersection)

        checker = NetworkCheck(self.task, {})

        # 'floating_ranges' and 'ip_ranges' have to be in the same 'cidr'
        # but don't intersect.
        checker.networks = [
            {'id': 1,
             'cidr': '192.168.0.0/25',
             'name': 'public',
             'gateway': '192.168.0.1',
             'ip_ranges': [['192.168.0.10', '192.168.0.40']],
             'meta': {'notation': 'cidr'},
             'group_id': 1,
             },
            {'id': 2,
             'cidr': '192.168.0.128/25',
             'name': 'public',
             'gateway': '192.168.0.129',
             'ip_ranges': [['192.168.0.130', '192.168.0.150']],
             'meta': {'notation': 'cidr'},
             'group_id': 2,
             }
        ]

        checker.network_config['floating_ranges'] = [
            ['192.168.0.50', '192.168.0.100'],
            ['192.168.0.160', '192.168.0.200']
        ]

        self.assertRaisesWithMessage(
            errors.NetworkCheckError,
            "Floating address ranges 192.168.0.50-192.168.0.100, "
            "192.168.0.160-192.168.0.200 are not in the same public CIDR.",
            checker.neutron_check_network_address_spaces_intersection)

    @patch.object(helpers, 'db')
    def test_check_non_shared_networks_intersection(self, _):
        checker = NetworkCheck(self.task, {})
        networks = [
            {'id': 1,
             'cidr': '192.168.0.0/25',
             'name': consts.NETWORKS.public,
             'gateway': '192.168.0.1',
             'ip_ranges': [['192.168.0.10', '192.168.0.40']],
             'meta': {'notation': consts.NETWORK_NOTATION.ip_ranges},
             'vlan_start': 111,
             'group_id': 1,
             },
            {'id': 2,
             'cidr': '192.168.0.0/25',
             'name': consts.NETWORKS.management,
             'gateway': '192.168.0.2',
             'ip_ranges': [['192.168.0.50', '192.168.0.110']],
             'meta': {'notation': consts.NETWORK_NOTATION.ip_ranges},
             'vlan_start': 222,
             'group_id': 1,
             }
        ]
        # different networks from one node group, different gateways
        checker.networks = networks
        self.assertRaisesWithMessage(
            errors.NetworkCheckError,
            "Address space intersection between networks:\n"
            "public, management",
            checker.neutron_check_network_address_spaces_intersection)

        checker = NetworkCheck(self.task, {})
        # different networks from different node groups, different gateways
        networks[1]['group_id'] = 2
        checker.networks = networks
        self.assertRaisesWithMessage(
            errors.NetworkCheckError,
            "Address space intersection between networks:\n"
            "public, management",
            checker.neutron_check_network_address_spaces_intersection)

        checker = NetworkCheck(self.task, {})
        # same networks from different node groups, different gateways
        networks[1]['name'] = consts.NETWORKS.public
        checker.networks = networks
        self.assertRaisesWithMessage(
            errors.NetworkCheckError,
            "Address space intersection between networks:\n"
            "public, public",
            checker.neutron_check_network_address_spaces_intersection)

        checker = NetworkCheck(self.task, {})
        # same networks from different node groups, same gateway
        networks[1]['gateway'] = '192.168.0.1'
        checker.networks = networks
        checker.network_config['floating_ranges'] = [
            ['192.168.0.111', '192.168.0.126']
        ]
        self.assertNotRaises(
            errors.NetworkCheckError,
            checker.check_configuration)

        checker = NetworkCheck(self.task, {})
        # same networks from different node groups, same gateway,
        # intersection in ip_ranges
        networks[1]['ip_ranges'] = [['192.168.0.30', '192.168.0.60']]
        checker.networks = networks
        checker.network_config['floating_ranges'] = [
            ['192.168.0.111', '192.168.0.126']
        ]
        self.assertNotRaises(
            errors.NetworkCheckError,
            checker.check_configuration)

    @patch.object(helpers, 'db')
    def test_check_vlan_ids_range_and_intersection_failed(self, mocked_db):
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'name': 'fixed',
                             'gateway': '192.168.0.1',
                             'vlan_start': 1}]
        checker.network_config['fixed_networks_vlan_start'] = 1
        checker.network_config['fixed_networks_amount'] = 10

        self.assertRaises(errors.NetworkCheckError,
                          checker.check_vlan_ids_range_and_intersection)

    @patch.object(helpers, 'db')
    def test_check_dns_equality(self, mocked_db):
        dns_lists = [
            (['2.3.4.5'], True),
            (['2.3.4.5', '2.3.4.5'], False),
            (['2.3.4.5', '2.3.4.99'], True),
            (['2.3.4.5', '2.3.4.99', '2.3.4.99'], False),
            (['2.3.4.5', '2.3.4.99', '2.3.4.199'], True),
        ]
        checker = NetworkCheck(self.task, {})
        for dns_setup, must_pass in dns_lists:
            checker.network_config['dns_nameservers'] = dns_setup

            if must_pass:
                self.assertNotRaises(errors.NetworkCheckError,
                                     checker.check_dns_servers_ips)
            else:
                self.assertRaises(errors.NetworkCheckError,
                                  checker.check_dns_servers_ips)

    @patch.object(helpers, 'db')
    def test_check_calculated_network_cidr(self, mocked_db):
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.99.0/16',
                             'name': 'storage',
                             'gateway': '192.168.0.1',
                             'vlan_start': 1}]

        self.assertRaises(errors.NetworkCheckError,
                          checker.check_calculated_network_cidr)

    @patch.object(helpers, 'db')
    def test_check_vlan_ids_range_and_intersection(self, mocked_db):
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'name': 'fixed',
                             'gateway': '192.168.0.1',
                             'vlan_start': 200}]
        checker.network_config['fixed_networks_vlan_start'] = 2
        checker.network_config['fixed_networks_amount'] = 10

        self.assertNotRaises(errors.NetworkCheckError,
                             checker.check_vlan_ids_range_and_intersection)

    @patch.object(helpers, 'db')
    def test_check_networks_amount(self, mocked_db):
        cluster = self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network},
            nodes_kwargs=[
                {"api": True,
                 "pending_addition": True},
            ])
        self.task = FakeTask(self.db.query(Cluster).get(cluster['id']))

        checker = NetworkCheck(self.task, {})
        checker.network_config['net_manager'] = 'FlatDHCPManager'
        checker.network_config['fixed_networks_amount'] = 2

        self.assertNotRaises(errors.NetworkCheckError,
                             checker.check_networks_amount)

        checker = NetworkCheck(self.task, {})
        checker.network_config['net_manager'] = 'FlatDHCPManager'
        checker.network_config['fixed_networks_amount'] = 1

        self.assertNotRaises(errors.NetworkCheckError,
                             checker.check_networks_amount)

        checker = NetworkCheck(self.task, {})
        checker.network_config['fixed_network_size'] = 100
        checker.network_config['fixed_networks_amount'] = 3
        checker.network_config['fixed_networks_cidr'] = '192.168.10.1/24'

        self.assertNotRaises(errors.NetworkCheckError,
                             checker.check_networks_amount)

        checker = NetworkCheck(self.task, {})
        checker.network_config['fixed_network_size'] = 10
        checker.network_config['fixed_networks_amount'] = 1
        checker.network_config['fixed_networks_cidr'] = '192.168.10.1/24'

        self.assertNotRaises(errors.NetworkCheckError,
                             checker.check_networks_amount)

    @patch.object(helpers, 'db')
    def test_neutron_check_l3_addresses_not_match_subnet_and_broadcast(
            self, mocked_db):
        checker = NetworkCheck(self.task, {})
        checker.network_config['floating_ranges'] = [('192.168.0.1',
                                                      '192.168.0.255')]
        checker.network_config['internal_cidr'] = '192.168.0.0/24'
        checker.network_config['internal_gateway'] = '192.168.0.0'
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'gateway': '192.168.0.1',
                             'name': 'public'}]
        self.assertRaises(
            errors.NetworkCheckError,
            checker.neutron_check_l3_addresses_not_match_subnet_and_broadcast)
        self.assertEqual(len(checker.err_msgs), 2)

    def test_check_network_classes_exclude_loopback(self):
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'cidr': '192.168.0.0/24'}]
        self.assertNotRaises(errors.NetworkCheckError,
                             checker.check_network_classes_exclude_loopback)

    @patch.object(helpers, 'db')
    def test_check_network_classes_exclude_loopback_fail(self, mocked_db):
        checker = NetworkCheck(self.task, {})
        networks = ['224.0.0.0/3', '127.0.0.0/8']
        for network in networks:
            checker.networks = [{'id': 1, 'cidr': network, 'name': 'fake'}]
            self.assertRaises(errors.NetworkCheckError,
                              checker.check_network_classes_exclude_loopback)
        self.assertEqual(mocked_db.call_count, 4)

    @patch.object(helpers, 'db')
    def test_check_network_addresses_not_match_subnet_and_broadcast(self,
                                                                    mocked_db):
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'gateway': '192.168.0.1',
                             'name': 'fake1',
                             'meta': {'notation': 'ip_ranges'}}]
        self.assertNotRaises(
            errors.NetworkCheckError,
            checker.check_network_addresses_not_match_subnet_and_broadcast)

        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'gateway': '192.168.0.0',
                             'name': 'fake1',
                             'meta': {'notation': 'ip_ranges'}}]
        self.assertRaises(
            errors.NetworkCheckError,
            checker.check_network_addresses_not_match_subnet_and_broadcast)

        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'ip_ranges': ['192.168.0.1', '192.168.0.100'],
                             'gateway': '192.168.0.0',
                             'name': 'fake1',
                             'meta': {'notation': 'ip_ranges'}}]
        self.assertRaises(
            errors.NetworkCheckError,
            checker.check_network_addresses_not_match_subnet_and_broadcast)

        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'ip_ranges': ['192.168.1.1', '192.168.1.100'],
                             'gateway': '192.168.0.1',
                             'name': 'fake1',
                             'meta': {'notation': 'ip_ranges'}}]
        self.assertNotRaises(
            errors.NetworkCheckError,
            checker.check_network_addresses_not_match_subnet_and_broadcast)

    def test_check_bond_slaves_speeds(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}
            ]
        )
        cluster_db = self.db.query(Cluster).get(cluster['id'])

        checker = NetworkCheck(FakeTask(cluster_db), {})
        checker.check_bond_slaves_speeds()

        self.assertEqual(checker.err_msgs, [])
        bond_if1 = node.NodeBondInterface()
        bond_if2 = node.NodeBondInterface()

        nic1 = node.NodeNICInterface()
        nic2 = node.NodeNICInterface()
        nic3 = node.NodeNICInterface()
        nic1.current_speed = 100
        nic2.current_speed = 10
        nic3.current_speed = None
        bond_if1.slaves = [nic1, nic2, nic3]
        bond_if2.slaves = [nic3]
        checker.cluster.nodes[0].bond_interfaces = [bond_if1, bond_if2]

        checker.check_bond_slaves_speeds()
        self.assertEqual(len(checker.err_msgs), 2)

    def test_check_configuration_neutron(self):
        checker = NetworkCheck(self.task, {})
        checker.net_provider = 'neutron'
        checker.neutron_check_network_address_spaces_intersection = MagicMock()
        checker.neutron_check_segmentation_ids = MagicMock()
        checker.neutron_check_l3_addresses_not_match_subnet_and_broadcast = \
            MagicMock()

        checker.check_public_floating_ranges_intersection = MagicMock()
        checker.check_network_address_spaces_intersection = MagicMock()
        checker.check_networks_amount = MagicMock()
        checker.check_vlan_ids_range_and_intersection = MagicMock()

        checker.check_network_classes_exclude_loopback = MagicMock()
        checker.check_network_addresses_not_match_subnet_and_broadcast = \
            MagicMock()

        checker.check_configuration()

        not_called = [
            'check_public_floating_ranges_intersection',
            'check_network_address_spaces_intersection',
            'check_networks_amount',
            'check_vlan_ids_range_and_intersection'
        ]
        for method in not_called:
            mocked = getattr(checker, method)
            self.assertFalse(mocked.called)

        called = [
            'neutron_check_network_address_spaces_intersection',
            'neutron_check_segmentation_ids',
            'neutron_check_l3_addresses_not_match_subnet_and_broadcast',
            'check_network_classes_exclude_loopback',
            'check_network_addresses_not_match_subnet_and_broadcast'
        ]
        for method in called:
            mocked = getattr(checker, method)
            mocked.assert_any_call()

    def test_check_configuration_nova_network(self):
        checker = NetworkCheck(self.task, {})
        checker.net_provider = 'nova-network'
        checker.neutron_check_network_address_spaces_intersection = MagicMock()
        checker.neutron_check_segmentation_ids = MagicMock()
        checker.neutron_check_l3_addresses_not_match_subnet_and_broadcast = \
            MagicMock()

        checker.check_public_floating_ranges_intersection = MagicMock()
        checker.check_network_address_spaces_intersection = MagicMock()
        checker.check_networks_amount = MagicMock()
        checker.check_vlan_ids_range_and_intersection = MagicMock()

        checker.check_network_classes_exclude_loopback = MagicMock()
        checker.check_network_addresses_not_match_subnet_and_broadcast = \
            MagicMock()

        checker.check_configuration()

        not_called = [
            'neutron_check_network_address_spaces_intersection',
            'neutron_check_segmentation_ids',
            'neutron_check_l3_addresses_not_match_subnet_and_broadcast'
        ]
        for method in not_called:
            mocked = getattr(checker, method)
            self.assertFalse(mocked.called)

        called = [
            'check_public_floating_ranges_intersection',
            'check_network_address_spaces_intersection',
            'check_networks_amount',
            'check_vlan_ids_range_and_intersection',
            'check_network_classes_exclude_loopback',
            'check_network_addresses_not_match_subnet_and_broadcast'
        ]
        for method in called:
            mocked = getattr(checker, method)
            mocked.assert_any_call()

    @patch.object(NetworkCheck, 'check_untagged_intersection')
    @patch.object(NetworkCheck, 'check_bond_slaves_speeds')
    def test_check_interface_mapping(self, mock_untagged, mock_bond):
        checker = NetworkCheck(self.task, {})
        checker.check_interface_mapping()
        mock_untagged.assert_called_with()
        mock_bond.assert_called_with()

    @patch.object(helpers, 'db')
    @patch('objects.NodeGroupCollection.get_by_cluster_id')
    def test_neutron_check_gateways_valid(self, get_by_cluster_id_mock,
                                          mocked_db):
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'gateway': '192.168.0.1',
                             'meta': {'notation': consts.NETWORK_NOTATION.cidr}
                             }]
        nodegroup_mock = MagicMock(**{'count.return_value': 2})
        get_by_cluster_id_mock.return_value = nodegroup_mock
        self.assertNotRaises(errors.NetworkCheckError,
                             checker.neutron_check_gateways)

    @patch.object(helpers, 'db')
    @patch('objects.NodeGroupCollection.get_by_cluster_id')
    def test_neutron_check_gateways_gw_none(self, get_by_cluster_id_mock,
                                            mocked_db):
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'gateway': None,
                             'meta': {'notation': consts.NETWORK_NOTATION.cidr}
                             }]
        nodegroup_mock = MagicMock(**{'count.return_value': 2})
        get_by_cluster_id_mock.return_value = nodegroup_mock
        self.assertRaises(errors.NetworkCheckError,
                          checker.neutron_check_gateways)

    @patch.object(helpers, 'db')
    @patch('objects.NodeGroupCollection.get_by_cluster_id')
    def test_neutron_check_gateways_gw_outside(self, get_by_cluster_id_mock,
                                               mocked_db):
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'gateway': '192.168.1.1',
                             'meta': {'notation': consts.NETWORK_NOTATION.cidr}
                             }]
        nodegroup_mock = MagicMock(**{'count.return_value': 2})
        get_by_cluster_id_mock.return_value = nodegroup_mock
        self.assertRaises(errors.NetworkCheckError,
                          checker.neutron_check_gateways)

    @patch.object(helpers, 'db')
    @patch('objects.NodeGroupCollection.get_by_cluster_id')
    def test_neutron_check_gateways_gw_in_range(self, get_by_cluster_id_mock,
                                                mocked_db):
        checker = NetworkCheck(self.task, {})
        checker.networks = [{'id': 1,
                             'cidr': '192.168.0.0/24',
                             'gateway': '192.168.0.75',
                             'ip_ranges': [('192.168.0.50', '192.168.0.100')],
                             'meta': {'notation': consts.NETWORK_NOTATION.cidr}
                             }]
        nodegroup_mock = MagicMock(**{'count.return_value': 2})
        get_by_cluster_id_mock.return_value = nodegroup_mock
        self.assertRaises(errors.NetworkCheckError,
                          checker.neutron_check_gateways)

    @patch.object(helpers, 'db')
    def test_check_network_template(self, mocked_db):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
            ]
        )

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        fake_template = self.env.read_fixtures(['network_template_80'])[0]
        default_nt = fake_template['adv_net_template']['default']

        # Left only default node group with only controller template
        fake_template['adv_net_template'] = {
            'default': default_nt
        }
        default_nt['templates_for_node_role'] = {
            'controller': default_nt['templates_for_node_role']['controller'],
            'compute': default_nt['templates_for_node_role']['compute']
        }
        fake_template.pop('pk')  # PK is not needed

        cluster_db.network_config.configuration_template = fake_template
        self.db.flush()
        checker = NetworkCheck(FakeTask(cluster_db), {})

        # Check valid template. It should not raise NetworkCheckError
        self.assertNotRaises(errors.NetworkCheckError,
                             checker.check_network_template)

        # Remove template for 'compute' network role
        default_nt['templates_for_node_role'].pop('compute')

        cluster_db.network_config.configuration_template = fake_template
        self.db.flush()
        checker = NetworkCheck(FakeTask(cluster_db), {})

        # node[1] is assigned to network role 'compute', so
        # fake_template is not valid and check should raise exception
        # NetworkCheckError
        self.assertRaises(errors.NetworkCheckError,
                          checker.check_network_template)


class TestCheckVIPsNames(BaseIntegrationTest):

    def setUp(self):
        super(TestCheckVIPsNames, self).setUp()

        self.env.create(
            release_kwargs={'version': 'liberty-8.0'},
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre,
            },
            nodes_kwargs=[{'roles': ['controller']}]
        )

        self.cluster = self.env.clusters[0]
        self.plugin = self.env.create_plugin(cluster=self.cluster)
        self.task = Task(cluster_id=self.cluster.id)
        self.db.add(self.task)
        self.db.flush()

    def test_fail_if_vips_for_cluster_are_not_unique(self):
        cluster_net_roles = self.cluster.release.network_roles_metadata
        cluster_net_roles[1]["properties"]["vip"].append({
            "name": "vip1"
        })
        cluster_net_roles[0]["properties"]["vip"].append({
            "name": "vip1"
        })
        self.db.flush()
        with self.assertRaises(errors.CheckBeforeDeploymentError) as exc:
            ApplyChangesTaskManager(self.cluster.id)\
                .check_before_deployment(self.task)

            self.assertIn('Duplicate VIP names found in network configuration',
                          exc.exception.message)

    def test_check_vip_names_is_merged(self):
        cluster_net_roles = self.cluster.release.network_roles_metadata
        cluster_net_roles[0]["properties"]["vip"].append({
            "name": "vip1", "namespace": "vip_ns1"
        })
        plugin_net_roles = [copy.deepcopy(cluster_net_roles[0])]
        plugin_net_roles[0]["properties"]["vip"] = [{
            "name": "vip1", "namespace": "vip_ns1"
        }]
        self.plugin.network_roles_metadata = plugin_net_roles
        self.db.flush()
        self.assertNotRaises(
            errors.CheckBeforeDeploymentError,
            ApplyChangesTaskManager(self.cluster.id)
            .check_before_deployment,
            self.task
        )

    def test_fail_if_vips_cannot_be_merged(self):
        cluster_net_roles = self.cluster.release.network_roles_metadata
        cluster_net_roles[0]["properties"]["vip"].append({
            "name": "vip1", "namespace": "vip_ns1"
        })
        plugin_net_roles = [copy.deepcopy(cluster_net_roles[0])]
        plugin_net_roles[0]["properties"]["vip"] = [{
            "name": "vip1", "namespace": "vip_ns2"
        }]
        self.plugin.network_roles_metadata = plugin_net_roles
        self.db.flush()
        with self.assertRaises(errors.CheckBeforeDeploymentError) as exc:
            ApplyChangesTaskManager(self.cluster.id)\
                .check_before_deployment(self.task)

            self.assertIn(
                'Cannot override existing network roles',
                exc.exception.message
            )
