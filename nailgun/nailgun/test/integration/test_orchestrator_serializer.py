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

import copy
from operator import attrgetter
from operator import itemgetter
from random import randint
import re
import six

import mock
from netaddr import IPAddress
from netaddr import IPNetwork
from netaddr import IPRange
from oslo.serialization import jsonutils

from nailgun import consts
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node

from nailgun.orchestrator.deployment_serializers import\
    DeploymentHASerializer
from nailgun.orchestrator.deployment_serializers import\
    DeploymentHASerializer50
from nailgun.orchestrator.deployment_serializers import\
    DeploymentHASerializer51
from nailgun.orchestrator.deployment_serializers import\
    DeploymentHASerializer61
from nailgun.orchestrator.deployment_serializers import\
    DeploymentMultinodeSerializer
from nailgun.orchestrator.deployment_serializers import\
    DeploymentMultinodeSerializer50
from nailgun.orchestrator.deployment_serializers import\
    DeploymentMultinodeSerializer61
from nailgun.orchestrator.deployment_serializers import\
    get_serializer_for_cluster


from nailgun.orchestrator.deployment_graph import AstuteGraph

from nailgun.db.sqlalchemy import models
from nailgun import objects

from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse
from nailgun.volumes import manager


class OrchestratorSerializerTestBase(BaseIntegrationTest):
    """Class containts helpers."""

    def setUp(self):
        super(OrchestratorSerializerTestBase, self).setUp()
        self.cluster_mock = mock.MagicMock(pending_release_id=None)
        self.cluster_mock.deployment_tasks = []
        self.cluster_mock.release.deployment_tasks = []

    def filter_by_role(self, nodes, role):
        return filter(lambda node: role in node['role'], nodes)

    def filter_by_uid(self, nodes, uid):
        return filter(lambda node: node['uid'] == uid, nodes)

    def assert_nodes_with_role(self, nodes, role, count):
        self.assertEqual(len(self.filter_by_role(nodes, role)), count)

    def get_controllers(self, cluster_id):
        return self.db.query(Node).\
            filter_by(cluster_id=cluster_id,
                      pending_deletion=False).\
            filter(Node.role_list.any(name='controller')).\
            order_by(Node.id)

    def add_default_params(self, nodes):
        """Adds neceserry default parameters to nodes

        :param nodes: list of dicts
        """
        for pos, node in enumerate(nodes, start=1):
            node['uid'] = str(pos)

    @property
    def serializer(self):
        with mock.patch(
                'nailgun.objects.release.extract_env_version',
                return_value='5.0'):
            return DeploymentHASerializer(AstuteGraph(self.cluster_mock))

    def serialize(self, cluster):
        objects.NodeCollection.prepare_for_deployment(cluster.nodes)
        return self.serializer.serialize(cluster, cluster.nodes)

    def _make_data_copy(self, data_to_copy):
        '''Sqalchemy doesn't track change on composite attribute
        so we need to create fresh copy of it which will take all
        needed modifications and will be assigned as new value
        for that attribute
        '''
        return copy.deepcopy(data_to_copy)

    def move_network(self, node_id, net_name, from_if, to_if):
        resp = self.app.get(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": node_id}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json_body

        net_from = None
        for nic in data:
            if nic['name'] == from_if:
                net_from = [n for n in nic['assigned_networks']
                            if n['name'] == net_name]
                if net_from:
                    nic['assigned_networks'] = \
                        [n for n in nic['assigned_networks']
                         if n != net_from[0]]
        self.assertIsNotNone(net_from)
        for nic in data:
            if nic['name'] == to_if:
                nic['assigned_networks'].append(net_from[0])

        resp = self.env.node_nics_put(node_id, data)
        self.assertEqual(resp.status_code, 200)

    def check_ep_format(self, endpoint_list):
        for ep in endpoint_list.values():
            if ep.get('IP'):
                self.assertTrue(
                    ep['IP'] == 'none' or isinstance(ep['IP'], list))


# TODO(awoodward): multinode deprecation: probably has duplicates
class TestNovaOrchestratorSerializer(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestNovaOrchestratorSerializer, self).setUp()
        self.cluster = self.create_env('ha_compact')
        objects.Cluster.set_primary_roles(self.cluster, self.cluster.nodes)

    def create_env(self, mode, network_manager='FlatDHCPManager',
                   env_version=None):
        release_kwargs = {}
        if env_version:
            release_kwargs['version'] = env_version

        node_args = [
            {'roles': ['controller', 'cinder'], 'pending_addition': True},
            {'roles': ['compute', 'cinder'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True},
            {'roles': ['mongo'], 'pending_addition': True},
            {'roles': [], 'pending_roles': ['cinder'],
             'pending_addition': True}]

        cluster = self.env.create(
            release_kwargs=release_kwargs,
            cluster_kwargs={
                'mode': mode,
                'net_manager': network_manager},
            nodes_kwargs=node_args)

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        self.db.flush()
        return cluster_db

    def assert_roles_flattened(self, nodes):
        self.assertEqual(len(nodes), 7)
        self.assert_nodes_with_role(nodes, 'controller', 1)
        self.assert_nodes_with_role(nodes, 'compute', 2)
        self.assert_nodes_with_role(nodes, 'cinder', 3)
        self.assert_nodes_with_role(nodes, 'mongo', 1)

    def test_serialize_nodes(self):
        serialized_nodes = self.serializer.serialize_nodes(self.cluster.nodes)
        self.assert_roles_flattened(serialized_nodes)

        # Each not should be same as result of
        # serialize_node function
        for serialized_node in serialized_nodes:
            node_db = self.db.query(Node).get(int(serialized_node['uid']))

            expected_node = self.serializer.serialize_node(
                node_db, serialized_node['role'])
            self.assertEqual(serialized_node, expected_node)

    def test_serialize_node(self):
        node = self.env.create_node(
            api=True, cluster_id=self.cluster.id, pending_addition=True)

        objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)
        self.db.flush()

        node_db = self.db.query(Node).get(node['id'])

        serialized_data = self.serializer.serialize_node(node_db, 'controller')

        self.assertEqual(serialized_data['role'], 'controller')
        self.assertEqual(serialized_data['uid'], str(node_db.id))
        self.assertEqual(serialized_data['status'], node_db.status)
        self.assertEqual(serialized_data['online'], node_db.online)
        self.assertEqual(serialized_data['fqdn'],
                         'node-%d.%s' % (node_db.id, settings.DNS_DOMAIN))
        self.assertEqual(
            serialized_data['glance'],
            {'image_cache_max_size': manager.calc_glance_cache_size(
                node_db.attributes.volumes)})

    def test_node_list(self):
        node_list = self.serializer.get_common_attrs(self.cluster)['nodes']

        # Check right nodes count with right roles
        self.assert_roles_flattened(node_list)

        # Check common attrs
        for node in node_list:
            node_db = self.db.query(Node).get(int(node['uid']))
            self.assertEqual(node['public_netmask'], '255.255.255.0')
            self.assertEqual(node['internal_netmask'], '255.255.255.0')
            self.assertEqual(node['storage_netmask'], '255.255.255.0')
            self.assertEqual(node['uid'], str(node_db.id))
            self.assertEqual(node['name'], 'node-%d' % node_db.id)
            self.assertEqual(node['fqdn'], 'node-%d.%s' %
                             (node_db.id, settings.DNS_DOMAIN))

        # Check uncommon attrs
        # Convert ids to int to have correct order in the set
        node_uids = sorted(set([int(n['uid']) for n in node_list]))
        man_ip = [str(ip) for ip in IPRange('192.168.0.1', '192.168.0.5')]
        pub_ip = [str(ip) for ip in IPRange('172.16.0.2', '172.16.0.6')]
        sto_ip = [str(ip) for ip in IPRange('192.168.1.1', '192.168.1.5')]
        expected_list = [
            {'roles': ['controller', 'cinder']},
            {'roles': ['compute', 'cinder']},
            {'roles': ['compute']},
            {'roles': ['mongo']},
            {'roles': ['cinder']}]
        for i in range(len(expected_list)):
            expected_list[i]['attrs'] = {'uid': str(node_uids[i])}

        used_man_ip = []
        used_pub_ip = []
        used_sto_ip = []

        for expected in expected_list:
            attrs = expected['attrs']

            ref_node = self.filter_by_uid(node_list, attrs['uid'])[0]
            self.assertTrue(ref_node['internal_address'] in man_ip)
            self.assertTrue(ref_node['public_address'] in pub_ip)
            self.assertTrue(ref_node['storage_address'] in sto_ip)
            self.assertFalse(ref_node['internal_address'] in used_man_ip)
            self.assertFalse(ref_node['public_address'] in used_pub_ip)
            self.assertFalse(ref_node['storage_address'] in used_sto_ip)
            used_man_ip.append(ref_node['internal_address'])
            used_pub_ip.append(ref_node['public_address'])
            used_sto_ip.append(ref_node['storage_address'])
            for role in expected['roles']:
                nodes = self.filter_by_role(node_list, role)
                node = self.filter_by_uid(nodes, attrs['uid'])[0]

                self.assertEqual(node['public_address'],
                                 ref_node['public_address'])
                self.assertEqual(node['storage_address'],
                                 ref_node['storage_address'])
                self.assertEqual(node['internal_address'],
                                 ref_node['internal_address'])

    def test_flatdhcp_manager(self):
        cluster = self.create_env('ha_compact')
        facts = self.serializer.serialize(cluster, cluster.nodes)
        for fact in facts:
            self.assertEqual(
                fact['novanetwork_parameters']['network_manager'],
                'FlatDHCPManager')
            self.assertEqual(
                fact['novanetwork_parameters']['num_networks'], 1)
            self.assertEqual(
                fact['novanetwork_parameters']['network_size'], 65536)

    def test_vlan_manager(self):
        cluster = self.create_env('ha_compact')
        data = {'networking_parameters': {'net_manager': 'VlanManager'}}
        url = reverse('NovaNetworkConfigurationHandler',
                      kwargs={'cluster_id': cluster.id})
        self.app.put(url, jsonutils.dumps(data),
                     headers=self.default_headers,
                     expect_errors=False)
        facts = self.serializer.serialize(cluster, cluster.nodes)

        for fact in facts:
            self.assertEqual(fact['vlan_interface'], 'eth0')
            self.assertEqual(fact['fixed_interface'], 'eth0')
            self.assertEqual(
                fact['novanetwork_parameters']['network_manager'],
                'VlanManager')
            self.assertEqual(
                fact['novanetwork_parameters']['num_networks'], 1)
            self.assertEqual(
                fact['novanetwork_parameters']['vlan_start'], 103)
            self.assertEqual(
                fact['novanetwork_parameters']['network_size'], 256)

    def test_floating_ranges_generation(self):
        # Set ip ranges for floating ips
        ranges = [['172.16.0.2', '172.16.0.4'],
                  ['172.16.0.3', '172.16.0.5'],
                  ['172.16.0.10', '172.16.0.12']]

        self.cluster.network_config.floating_ranges = ranges
        self.db.commit()

        facts = self.serializer.serialize(self.cluster, self.cluster.nodes)
        for fact in facts:
            self.assertEqual(
                fact['floating_network_range'],
                ['172.16.0.2-172.16.0.4',
                 '172.16.0.3-172.16.0.5',
                 '172.16.0.10-172.16.0.12'])

    def test_configure_interfaces_untagged_network(self):
        for network in self.db.query(NetworkGroup).all():
            network.vlan_start = None
        self.cluster.network_config.fixed_networks_vlan_start = None
        self.db.commit()
        node_db = sorted(self.cluster.nodes, key=lambda n: n.id)[0]
        from nailgun.orchestrator.deployment_serializers \
            import NovaNetworkDeploymentSerializer
        interfaces = NovaNetworkDeploymentSerializer.\
            configure_interfaces(node_db)

        expected_interfaces = {
            'lo': {
                'interface': 'lo',
                'ipaddr': ['127.0.0.1/8']
            },
            'eth1': {
                'interface': 'eth1',
                'ipaddr': ['10.20.0.129/24']
            },
            'eth0': {
                'interface': 'eth0',
                'ipaddr': ['172.16.0.2/24',
                           '192.168.0.1/24',
                           '192.168.1.1/24'],
                'gateway': '172.16.0.1',
                'default_gateway': True
            }
        }
        self.datadiff(expected_interfaces, interfaces, ignore_keys=['ipaddr'])

    def test_set_deployment_priorities(self):
        nodes = [
            {'role': 'mongo'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'controller'},
            {'role': 'ceph-osd'}
        ]
        self.add_default_params(nodes)
        with mock.patch(
                'nailgun.objects.release.extract_env_version',
                return_value='5.0'):
            serializer = DeploymentMultinodeSerializer(
                AstuteGraph(self.cluster_mock))
        serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'mongo', 'priority': 100},
            {'role': 'mongo', 'priority': 200},
            {'role': 'primary-mongo', 'priority': 300},
            {'role': 'controller', 'priority': 400},
            {'role': 'ceph-osd', 'priority': 500}
        ]
        self.add_default_params(expected_priorities)
        self.assertEqual(expected_priorities, nodes)

    def test_set_critital_node(self):
        nodes = [
            {'role': 'mongo'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'controller'},
            {'role': 'ceph-osd'}
        ]
        with mock.patch(
                'nailgun.objects.release.extract_env_version',
                return_value='5.0'):
            serializer = DeploymentMultinodeSerializer(
                AstuteGraph(self.cluster_mock))
        serializer.set_critical_nodes(nodes)
        expected_ciritial_roles = [
            {'role': 'mongo', 'fail_if_error': False},
            {'role': 'mongo', 'fail_if_error': False},
            {'role': 'primary-mongo', 'fail_if_error': True},
            {'role': 'controller', 'fail_if_error': True},
            {'role': 'ceph-osd', 'fail_if_error': True}
        ]
        self.assertEqual(expected_ciritial_roles, nodes)


class TestNovaNetworkOrchestratorSerializer61(OrchestratorSerializerTestBase):

    def create_env(self, manager, nodes_count=3, ctrl_count=1, nic_count=2):
        cluster = self.env.create(
            release_kwargs={'version': '2014.2-6.1'},
            cluster_kwargs={'mode': 'ha_compact'}
        )

        data = {'networking_parameters': {'net_manager': manager}}
        self.env.nova_networks_put(cluster['id'], data)

        self.env.create_nodes_w_interfaces_count(
            nodes_count=ctrl_count,
            if_count=nic_count,
            roles=['controller', 'cinder'],
            pending_addition=True,
            cluster_id=cluster['id'])
        self.env.create_nodes_w_interfaces_count(
            nodes_count=nodes_count - ctrl_count,
            if_count=nic_count,
            roles=['compute'],
            pending_addition=True,
            cluster_id=cluster['id'])

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        objects.Cluster.set_primary_roles(cluster_db, cluster_db.nodes)
        self.db.flush()
        return cluster_db

    def test_flat_dhcp_schema(self):
        cluster = self.create_env(
            manager=consts.NOVA_NET_MANAGERS.FlatDHCPManager
        )
        serializer = get_serializer_for_cluster(cluster)
        facts = serializer(AstuteGraph(cluster)).serialize(
            cluster, cluster.nodes)
        for node in facts:
            scheme = node['network_scheme']
            self.assertEqual(
                set(scheme.keys()),
                set(['version', 'provider', 'interfaces',
                     'endpoints', 'roles', 'transformations'])
            )
            self.assertEqual(scheme['version'], '1.1')
            self.assertEqual(scheme['provider'], 'lnx')
            self.assertEqual(
                set(scheme['interfaces'].keys()),
                set(['eth0', 'eth1'])
            )
            self.assertEqual(
                set(scheme['endpoints'].keys()),
                set(['br-storage', 'br-mgmt', 'br-fw-admin', 'br-ex',
                     'eth0.103'])
            )
            self.check_ep_format(scheme['endpoints'])
            self.assertEqual(
                scheme['roles'],
                {'storage': 'br-storage',
                 'management': 'br-mgmt',
                 'fw-admin': 'br-fw-admin',
                 'ex': 'br-ex',
                 'novanetwork/fixed': 'eth0.103'}
            )
            self.assertEqual(
                scheme['transformations'],
                [
                    {'action': 'add-br',
                     'name': 'br-fw-admin'},
                    {'action': 'add-br',
                     'name': 'br-storage'},
                    {'action': 'add-br',
                     'name': 'br-mgmt'},
                    {'action': 'add-br',
                     'name': 'br-ex'},
                    {'action': 'add-port',
                     'bridge': 'br-fw-admin',
                     'name': 'eth0'},
                    {'action': 'add-port',
                     'bridge': 'br-storage',
                     'name': 'eth0.102'},
                    {'action': 'add-port',
                     'bridge': 'br-mgmt',
                     'name': 'eth0.101'},
                    {'action': 'add-port',
                     'bridge': 'br-ex',
                     'name': 'eth1'},
                    {'action': 'add-port',
                     'name': 'eth0.103'},
                ]
            )

    def test_vlan_schema(self):
        cluster = self.create_env(
            manager=consts.NOVA_NET_MANAGERS.VlanManager
        )
        serializer = get_serializer_for_cluster(cluster)
        facts = serializer(AstuteGraph(cluster)).serialize(
            cluster, cluster.nodes)
        for node in facts:
            scheme = node['network_scheme']
            self.assertEqual(
                set(scheme.keys()),
                set(['version', 'provider', 'interfaces',
                     'endpoints', 'roles', 'transformations'])
            )
            self.assertEqual(scheme['version'], '1.1')
            self.assertEqual(scheme['provider'], 'lnx')
            self.assertEqual(
                set(scheme['interfaces'].keys()),
                set(['eth0', 'eth1'])
            )
            self.assertEqual(
                set(scheme['endpoints'].keys()),
                set(['br-storage', 'br-mgmt', 'br-fw-admin', 'br-ex',
                     'eth0'])
            )
            self.check_ep_format(scheme['endpoints'])
            self.assertEqual(
                scheme['roles'],
                {'storage': 'br-storage',
                 'management': 'br-mgmt',
                 'fw-admin': 'br-fw-admin',
                 'ex': 'br-ex',
                 'novanetwork/vlan': 'eth0'}
            )
            self.assertEqual(
                scheme['transformations'],
                [
                    {'action': 'add-br',
                     'name': 'br-fw-admin'},
                    {'action': 'add-br',
                     'name': 'br-storage'},
                    {'action': 'add-br',
                     'name': 'br-mgmt'},
                    {'action': 'add-br',
                     'name': 'br-ex'},
                    {'action': 'add-port',
                     'bridge': 'br-fw-admin',
                     'name': 'eth0'},
                    {'action': 'add-port',
                     'bridge': 'br-storage',
                     'name': 'eth0.102'},
                    {'action': 'add-port',
                     'bridge': 'br-mgmt',
                     'name': 'eth0.101'},
                    {'action': 'add-port',
                     'bridge': 'br-ex',
                     'name': 'eth1'},
                ]
            )

    def test_flat_dhcp_with_bonds(self):
        cluster = self.create_env(
            manager=consts.NOVA_NET_MANAGERS.FlatDHCPManager,
            ctrl_count=3,
            nic_count=3
        )
        for node in cluster.nodes:
            self.move_network(node.id, 'management', 'eth0', 'eth1')
            self.env.make_bond_via_api('lnx_bond',
                                       '',
                                       ['eth1', 'eth2'],
                                       node.id,
                                       bond_properties={
                                           'mode': consts.BOND_MODES.balance_rr
                                       })
        serializer = get_serializer_for_cluster(cluster)
        facts = serializer(AstuteGraph(cluster)).serialize(
            cluster, cluster.nodes)
        for node in facts:
            self.assertEqual(
                node['network_scheme']['transformations'],
                [
                    {'action': 'add-br',
                     'name': 'br-fw-admin'},
                    {'action': 'add-br',
                     'name': 'br-storage'},
                    {'action': 'add-br',
                     'name': 'br-mgmt'},
                    {'action': 'add-br',
                     'name': 'br-ex'},
                    {'action': 'add-port',
                     'bridge': 'br-fw-admin',
                     'name': 'eth0'},
                    {'action': 'add-port',
                     'bridge': 'br-storage',
                     'name': 'eth0.102'},
                    {'action': 'add-bond',
                     'bridge': 'br-ex',
                     'name': 'lnx_bond',
                     'interfaces': ['eth1', 'eth2'],
                     'bond_properties': {'mode': 'balance-rr'},
                     'interface_properties': {}},
                    {'action': 'add-port',
                     'bridge': 'br-mgmt',
                     'name': 'lnx_bond.101'},
                    {'action': 'add-port',
                     'name': 'eth0.103'},
                ]
            )

    def test_vlan_with_bonds(self):
        cluster = self.create_env(
            manager=consts.NOVA_NET_MANAGERS.VlanManager,
            ctrl_count=3,
            nic_count=3
        )
        for node in cluster.nodes:
            self.move_network(node.id, 'management', 'eth0', 'eth1')
            self.env.make_bond_via_api('lnx_bond',
                                       '',
                                       ['eth1', 'eth2'],
                                       node.id,
                                       bond_properties={
                                           'mode': consts.BOND_MODES.balance_rr
                                       })
        serializer = get_serializer_for_cluster(cluster)
        facts = serializer(AstuteGraph(cluster)).serialize(
            cluster, cluster.nodes)
        for node in facts:
            self.assertEqual(
                node['network_scheme']['transformations'],
                [
                    {'action': 'add-br',
                     'name': 'br-fw-admin'},
                    {'action': 'add-br',
                     'name': 'br-storage'},
                    {'action': 'add-br',
                     'name': 'br-mgmt'},
                    {'action': 'add-br',
                     'name': 'br-ex'},
                    {'action': 'add-port',
                     'bridge': 'br-fw-admin',
                     'name': 'eth0'},
                    {'action': 'add-port',
                     'bridge': 'br-storage',
                     'name': 'eth0.102'},
                    {'action': 'add-bond',
                     'bridge': 'br-ex',
                     'name': 'lnx_bond',
                     'interfaces': ['eth1', 'eth2'],
                     'bond_properties': {'mode': 'balance-rr'},
                     'interface_properties': {}},
                    {'action': 'add-port',
                     'bridge': 'br-mgmt',
                     'name': 'lnx_bond.101'},
                ]
            )


class TestNeutronOrchestratorSerializer61(OrchestratorSerializerTestBase):

    def create_env(self, segment_type, nodes_count=3, ctrl_count=1,
                   nic_count=2):
        cluster = self.env.create(
            release_kwargs={'version': '2014.2-6.1'},
            cluster_kwargs={
                'mode': 'ha_compact',
                'net_provider': 'neutron',
                'net_segment_type': segment_type}
        )
        self.env.create_nodes_w_interfaces_count(
            nodes_count=ctrl_count,
            if_count=nic_count,
            roles=['controller', 'cinder'],
            pending_addition=True,
            cluster_id=cluster['id'])
        self.env.create_nodes_w_interfaces_count(
            nodes_count=nodes_count - ctrl_count,
            if_count=nic_count,
            roles=['compute'],
            pending_addition=True,
            cluster_id=cluster['id'])

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        objects.Cluster.set_primary_roles(cluster_db, cluster_db.nodes)
        self.db.flush()
        return cluster_db

    def add_nics_properties(self, cluster):
        nodes_list = []
        for node in cluster.nodes:
            resp = self.app.get(
                reverse('NodeNICsHandler', kwargs={'node_id': node.id}),
                headers=self.default_headers
            )
            self.assertEquals(200, resp.status_code)
            interfaces = jsonutils.loads(resp.body)
            for iface in interfaces:
                self.assertEqual(iface['interface_properties'],
                                 {
                                     'mtu': None,
                                     'disable_offloading': False
                                 })
                if iface['name'] == 'eth0':
                    iface['interface_properties'] = {
                        'mtu': 1500,
                        'disable_offloading': True
                    }
            nodes_list.append({'id': node.id, 'interfaces': interfaces})
        resp_put = self.app.put(
            reverse('NodeCollectionNICsHandler'),
            jsonutils.dumps(nodes_list),
            headers=self.default_headers
        )
        self.assertEqual(resp_put.status_code, 200)

    def check_gateways(self, node, scheme, is_public):
        nm = objects.Node.get_network_manager(node)
        if is_public:
            gw = nm.get_node_network_by_netname(node, 'public')['gateway']
            self.assertEqual(scheme['endpoints']['br-ex']['gateway'], gw)
        else:
            gw = nm.assign_vips_for_net_groups(node.cluster)[
                'management_vrouter_vip']
            self.assertEqual(scheme['endpoints']['br-mgmt']['gateway'], gw)

    def test_vlan_schema(self):
        cluster = self.create_env(segment_type='vlan')
        self.add_nics_properties(cluster)
        serializer = get_serializer_for_cluster(cluster)
        facts = serializer(AstuteGraph(cluster)).serialize(
            cluster, cluster.nodes)
        for node in facts:
            node_db = objects.Node.get_by_uid(node['uid'])
            is_public = objects.Node.should_have_public(node_db)
            scheme = node['network_scheme']
            self.assertEqual(
                set(scheme.keys()),
                set(['version', 'provider', 'interfaces',
                     'endpoints', 'roles', 'transformations'])
            )
            self.assertEqual(scheme['version'], '1.1')
            self.assertEqual(scheme['provider'], 'lnx')
            self.assertEqual(
                scheme['interfaces'],
                {'eth0': {'mtu': 1500,
                          'vendor_specific': {
                              'disable_offloading': True}},
                 'eth1': {}}
            )
            br_set = set(['br-storage', 'br-mgmt', 'br-fw-admin', 'br-prv'])
            role_dict = {'storage': 'br-storage',
                         'management': 'br-mgmt',
                         'fw-admin': 'br-fw-admin',
                         'neutron/private': 'br-prv'}
            if is_public:
                br_set.update(['br-ex', 'br-floating'])
                role_dict.update({'ex': 'br-ex',
                                  'neutron/floating': 'br-floating'})
            self.assertEqual(
                set(scheme['endpoints'].keys()),
                br_set
            )
            self.check_ep_format(scheme['endpoints'])
            self.check_gateways(node_db, scheme, is_public)
            self.assertEqual(
                scheme['roles'],
                role_dict
            )
            transformations = [
                {'action': 'add-br',
                 'name': 'br-fw-admin'},
                {'action': 'add-br',
                 'name': 'br-mgmt'},
                {'action': 'add-br',
                 'name': 'br-storage'},
                {'action': 'add-br',
                 'name': 'br-ex'},
                {'action': 'add-br',
                 'name': 'br-floating',
                 'provider': 'ovs'},
                {'action': 'add-patch',
                 'bridges': ['br-floating', 'br-ex'],
                 'provider': 'ovs'},
                {'action': 'add-br',
                 'name': 'br-prv',
                 'provider': 'ovs'},
                {'action': 'add-patch',
                 'bridges': ['br-prv', 'br-fw-admin'],
                 'provider': 'ovs'},
                {'action': 'add-port',
                 'bridge': 'br-fw-admin',
                 'name': 'eth0'},
                {'action': 'add-port',
                 'bridge': 'br-storage',
                 'name': 'eth0.102'},
                {'action': 'add-port',
                 'bridge': 'br-mgmt',
                 'name': 'eth0.101'},
                {'action': 'add-port',
                 'bridge': 'br-ex',
                 'name': 'eth1'}
            ]
            if not is_public:
                # exclude all 'br-ex' and 'br-floating' objects
                transformations = transformations[:3] + transformations[6:11]
            self.assertEqual(
                scheme['transformations'],
                transformations
            )

    def test_vlan_with_bond(self):
        cluster = self.create_env(segment_type='vlan', ctrl_count=3,
                                  nic_count=3)
        for node in cluster.nodes:
            self.move_network(node.id, 'storage', 'eth0', 'eth1')
            self.env.make_bond_via_api('lnx_bond',
                                       '',
                                       ['eth1', 'eth2'],
                                       node.id,
                                       bond_properties={
                                           'mode': consts.BOND_MODES.balance_rr
                                       },
                                       interface_properties={
                                           'mtu': 9000
                                       })
        serializer = get_serializer_for_cluster(cluster)
        facts = serializer(AstuteGraph(cluster)).serialize(
            cluster, cluster.nodes)
        for node in facts:
            transformations = [
                {'action': 'add-br',
                 'name': 'br-fw-admin'},
                {'action': 'add-br',
                 'name': 'br-mgmt'},
                {'action': 'add-br',
                 'name': 'br-storage'},
                {'action': 'add-br',
                 'name': 'br-ex'},
                {'action': 'add-br',
                 'name': 'br-floating',
                 'provider': 'ovs'},
                {'action': 'add-patch',
                 'bridges': ['br-floating', 'br-ex'],
                 'provider': 'ovs'},
                {'action': 'add-br',
                 'name': 'br-prv',
                 'provider': 'ovs'},
                {'action': 'add-patch',
                 'bridges': ['br-prv', 'br-fw-admin'],
                 'provider': 'ovs'},
                {'action': 'add-port',
                 'bridge': 'br-fw-admin',
                 'name': 'eth0'},
                {'action': 'add-port',
                 'bridge': 'br-mgmt',
                 'name': 'eth0.101'},
                {'action': 'add-bond',
                 'bridge': 'br-ex',
                 'name': 'lnx_bond',
                 'interfaces': ['eth1', 'eth2'],
                 'bond_properties': {'mode': 'balance-rr'},
                 'interface_properties': {'mtu': 9000}},
                {'action': 'add-port',
                 'bridge': 'br-storage',
                 'name': 'lnx_bond.102'},
            ]
            self.assertEqual(
                node['network_scheme']['transformations'],
                transformations
            )

    def test_gre_schema(self):
        cluster = self.create_env(segment_type='gre')
        self.add_nics_properties(cluster)
        serializer = get_serializer_for_cluster(cluster)
        facts = serializer(AstuteGraph(cluster)).serialize(
            cluster, cluster.nodes)
        for node in facts:
            node_db = objects.Node.get_by_uid(node['uid'])
            is_public = objects.Node.should_have_public(node_db)
            scheme = node['network_scheme']
            self.assertEqual(
                set(scheme.keys()),
                set(['version', 'provider', 'interfaces',
                     'endpoints', 'roles', 'transformations'])
            )
            self.assertEqual(scheme['version'], '1.1')
            self.assertEqual(scheme['provider'], 'lnx')
            self.assertEqual(
                scheme['interfaces'],
                {'eth0': {'mtu': 1500,
                          'vendor_specific': {
                              'disable_offloading': True}},
                 'eth1': {}}
            )
            br_set = set(['br-storage', 'br-mgmt', 'br-fw-admin'])
            role_dict = {'storage': 'br-storage',
                         'management': 'br-mgmt',
                         'fw-admin': 'br-fw-admin',
                         'neutron/mesh': 'br-mgmt'}
            if is_public:
                br_set.update(['br-ex', 'br-floating'])
                role_dict.update({'ex': 'br-ex',
                                  'neutron/floating': 'br-floating'})
            self.assertEqual(
                set(scheme['endpoints'].keys()),
                br_set
            )
            self.check_ep_format(scheme['endpoints'])
            self.check_gateways(node_db, scheme, is_public)
            self.assertEqual(
                scheme['roles'],
                role_dict
            )
            transformations = [
                {'action': 'add-br',
                 'name': 'br-fw-admin'},
                {'action': 'add-br',
                 'name': 'br-mgmt'},
                {'action': 'add-br',
                 'name': 'br-storage'},
                {'action': 'add-br',
                 'name': 'br-ex'},
                {'action': 'add-br',
                 'name': 'br-floating',
                 'provider': 'ovs'},
                {'action': 'add-patch',
                 'bridges': ['br-floating', 'br-ex'],
                 'provider': 'ovs'},
                {'action': 'add-port',
                 'bridge': 'br-fw-admin',
                 'name': 'eth0'},
                {'action': 'add-port',
                 'bridge': 'br-storage',
                 'name': 'eth0.102'},
                {'action': 'add-port',
                 'bridge': 'br-mgmt',
                 'name': 'eth0.101'},
                {'action': 'add-port',
                 'bridge': 'br-ex',
                 'name': 'eth1'}
            ]
            if not is_public:
                # exclude all 'br-ex' and 'br-floating' objects
                transformations = transformations[:3] + transformations[6:9]
            self.assertEqual(
                scheme['transformations'],
                transformations
            )

    def test_gre_with_bond(self):
        cluster = self.create_env(segment_type='gre', ctrl_count=3,
                                  nic_count=3)
        for node in cluster.nodes:
            self.move_network(node.id, 'storage', 'eth0', 'eth1')
            self.env.make_bond_via_api(
                'lnx_bond',
                '',
                ['eth1', 'eth2'],
                node.id,
                bond_properties={
                    'mode': consts.BOND_MODES.l_802_3ad,
                    'xmit_hash_policy': consts.BOND_XMIT_HASH_POLICY.layer2,
                    'lacp_rate': consts.BOND_LACP_RATES.slow,
                    'type__': consts.BOND_TYPES.linux
                },
                interface_properties={
                    'mtu': 9000
                })
        serializer = get_serializer_for_cluster(cluster)
        facts = serializer(AstuteGraph(cluster)).serialize(
            cluster, cluster.nodes)
        for node in facts:
            transformations = [
                {'action': 'add-br',
                 'name': 'br-fw-admin'},
                {'action': 'add-br',
                 'name': 'br-mgmt'},
                {'action': 'add-br',
                 'name': 'br-storage'},
                {'action': 'add-br',
                 'name': 'br-ex'},
                {'action': 'add-br',
                 'name': 'br-floating',
                 'provider': 'ovs'},
                {'action': 'add-patch',
                 'bridges': ['br-floating', 'br-ex'],
                 'provider': 'ovs'},
                {'action': 'add-port',
                 'bridge': 'br-fw-admin',
                 'name': 'eth0'},
                {'action': 'add-port',
                 'bridge': 'br-mgmt',
                 'name': 'eth0.101'},
                {'action': 'add-bond',
                 'bridge': 'br-ex',
                 'name': 'lnx_bond',
                 'interfaces': ['eth1', 'eth2'],
                 'bond_properties': {'mode': '802.3ad',
                                     'xmit_hash_policy': 'layer2',
                                     'lacp_rate': 'slow'},
                 'interface_properties': {'mtu': 9000}},
                {'action': 'add-port',
                 'bridge': 'br-storage',
                 'name': 'lnx_bond.102'},
            ]
            self.assertEqual(
                node['network_scheme']['transformations'],
                transformations
            )

    def test_gre_with_multi_groups(self):
        cluster = self.create_env(segment_type='gre', ctrl_count=3)

        resp = self.env.create_node_group()
        group_id = resp.json_body['id']

        self.env.create_nodes_w_interfaces_count(
            nodes_count=3,
            if_count=2,
            roles=['compute'],
            pending_addition=True,
            cluster_id=cluster.id,
            group_id=group_id)

        nets = self.env.neutron_networks_get(cluster.id).json_body
        nets_w_gw = {'management': '199.99.20.0/24',
                     'storage': '199.98.20.0/24',
                     'fuelweb_admin': '199.97.20.0/24',
                     'public': '199.96.20.0/24'}
        for net in nets['networks']:
            if net['name'] in nets_w_gw.keys():
                if net['group_id'] == group_id:
                    net['cidr'] = nets_w_gw[net['name']]
                    net['ip_ranges'] = [[
                        str(IPAddress(IPNetwork(net['cidr']).first + 2)),
                        str(IPAddress(IPNetwork(net['cidr']).first + 253)),
                    ]]
                net['gateway'] = str(
                    IPAddress(IPNetwork(net['cidr']).first + 1))
        resp = self.env.neutron_networks_put(cluster.id, nets)
        self.assertEqual(resp.status_code, 200)

        objects.NodeCollection.prepare_for_deployment(cluster.nodes)
        serializer = get_serializer_for_cluster(cluster)
        facts = serializer(AstuteGraph(cluster)).serialize(
            cluster, cluster.nodes)

        for node in facts:
            node_db = objects.Node.get_by_uid(node['uid'])
            is_public = objects.Node.should_have_public(node_db)
            endpoints = node['network_scheme']['endpoints']
            br_set = set(['br-storage', 'br-mgmt', 'br-fw-admin'])
            if is_public:
                br_set.add('br-ex')
                # floating network won't have routes
                self.assertEqual(endpoints['br-floating'], {'IP': 'none'})
                endpoints.pop('br-floating')
            self.assertEqual(
                set(endpoints.keys()),
                br_set
            )
            for name, descr in six.iteritems(endpoints):
                self.assertTrue(set(['IP', 'routes']) <= set(descr.keys()))
                self.assertEqual(len(descr['routes']), 1)
                for route in descr['routes']:
                    self.assertEqual(set(['net', 'via']), set(route.keys()))


class TestNovaOrchestratorHASerializer(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestNovaOrchestratorHASerializer, self).setUp()
        self.cluster = self.create_env('ha_compact')
        objects.Cluster.set_primary_roles(self.cluster, self.cluster.nodes)

    def create_env(self, mode):
        cluster = self.env.create(
            cluster_kwargs={
                'mode': mode,
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller', 'cinder'], 'pending_addition': True},
                {'roles': ['compute', 'cinder'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['mongo'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}])

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    @property
    def serializer(self):
        with mock.patch(
                'nailgun.objects.release.extract_env_version',
                return_value='5.0'):
            return DeploymentHASerializer(AstuteGraph(self.cluster_mock))

    def test_set_deployment_priorities(self):
        nodes = [
            {'role': 'zabbix-server'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'primary-controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'ceph-osd'}
        ]
        self.add_default_params(nodes)
        self.serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'zabbix-server', 'priority': 100},
            {'role': 'mongo', 'priority': 200},
            {'role': 'primary-mongo', 'priority': 300},
            {'role': 'primary-controller', 'priority': 400},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 600},
            {'role': 'ceph-osd', 'priority': 700},
        ]
        self.add_default_params(expected_priorities)
        self.assertEqual(expected_priorities, nodes)

    def test_set_deployment_priorities_many_cntrls(self):
        nodes = [
            {'role': 'zabbix-server'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'primary-controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'ceph-osd'}
        ]
        self.add_default_params(nodes)
        self.serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'zabbix-server', 'priority': 100},
            {'role': 'mongo', 'priority': 200},
            {'role': 'primary-mongo', 'priority': 300},
            {'role': 'primary-controller', 'priority': 400},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 600},
            {'role': 'controller', 'priority': 700},
            {'role': 'controller', 'priority': 800},
            {'role': 'controller', 'priority': 900},
            {'role': 'controller', 'priority': 1000},
            {'role': 'controller', 'priority': 1100},
            {'role': 'controller', 'priority': 1200},
            {'role': 'ceph-osd', 'priority': 1300}
        ]
        self.add_default_params(expected_priorities)
        self.assertEqual(expected_priorities, nodes)

    def test_set_critital_node(self):
        nodes = [
            {'role': 'zabbix-server'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'primary-controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'ceph-osd'}
        ]
        self.serializer.set_critical_nodes(nodes)
        expected_ciritial_roles = [
            {'role': 'zabbix-server', 'fail_if_error': False},
            {'role': 'mongo', 'fail_if_error': False},
            {'role': 'primary-mongo', 'fail_if_error': True},
            {'role': 'primary-controller', 'fail_if_error': True},
            {'role': 'controller', 'fail_if_error': False},
            {'role': 'controller', 'fail_if_error': False},
            {'role': 'ceph-osd', 'fail_if_error': True}
        ]
        self.assertEqual(expected_ciritial_roles, nodes)

    def test_set_primary_controller_priority_not_depend_on_nodes_order(self):
        controllers = filter(lambda n: 'controller' in n.roles, self.env.nodes)
        expected_primary_controller = sorted(
            controllers, key=attrgetter('id'))[0]
        reverse_sorted_controllers = sorted(
            controllers, key=attrgetter('id'), reverse=True)

        result_nodes = self.serializer.serialize(
            self.cluster, reverse_sorted_controllers)

        high_priority = sorted(result_nodes, key=itemgetter('priority'))[0]
        self.assertEqual(high_priority['role'], 'primary-controller')
        self.assertEqual(
            int(high_priority['uid']),
            expected_primary_controller.id)

    def test_node_list(self):
        serialized_nodes = self.serializer.node_list(self.cluster.nodes)

        for node in serialized_nodes:
            # Each node has swift_zone
            self.assertEqual(node['swift_zone'], node['uid'])

    def test_get_common_attrs(self):
        attrs = self.serializer.get_common_attrs(self.cluster)
        # vips
        self.assertEqual(attrs['management_vip'], '192.168.0.8')
        self.assertEqual(attrs['public_vip'], '172.16.0.9')

        # last_contrller
        controllers = self.get_controllers(self.cluster.id)
        self.assertEqual(attrs['last_controller'],
                         'node-%d' % controllers[-1].id)

        # primary_controller
        controllers = self.filter_by_role(attrs['nodes'], 'primary-controller')
        self.assertEqual(controllers[0]['role'], 'primary-controller')

        # primary_mongo
        mongo_nodes = self.filter_by_role(attrs['nodes'], 'primary-mongo')
        self.assertEqual(mongo_nodes[-1]['role'], 'primary-mongo')

        # mountpoints and mp attrs
        self.assertEqual(
            attrs['mp'],
            [{'point': '1', 'weight': '1'},
             {'point': '2', 'weight': '2'}])


class TestNovaOrchestratorHASerializer51(TestNovaOrchestratorHASerializer):

    @property
    def serializer(self):
        with mock.patch(
                'nailgun.objects.release.extract_env_version',
                return_value='5.1'):
            return DeploymentHASerializer51(AstuteGraph(self.cluster_mock))

    def test_set_deployment_priorities(self):
        nodes = [
            {'role': 'zabbix-server'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'primary-controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'ceph-osd'}
        ]
        self.add_default_params(nodes)
        self.serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'zabbix-server', 'priority': 100},
            {'role': 'mongo', 'priority': 200},
            {'role': 'primary-mongo', 'priority': 300},
            {'role': 'primary-controller', 'priority': 400},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 500},
            {'role': 'ceph-osd', 'priority': 600},
        ]
        self.add_default_params(expected_priorities)
        self.assertEqual(expected_priorities, nodes)

    def test_set_deployment_priorities_many_cntrls(self):
        nodes = [
            {'role': 'zabbix-server'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'primary-controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'ceph-osd'}
        ]
        self.add_default_params(nodes)
        self.serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'zabbix-server', 'priority': 100},
            {'role': 'mongo', 'priority': 200},
            {'role': 'primary-mongo', 'priority': 300},
            {'role': 'primary-controller', 'priority': 400},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 600},
            {'role': 'controller', 'priority': 600},
            {'role': 'ceph-osd', 'priority': 700}
        ]
        self.add_default_params(expected_priorities)
        self.assertEqual(expected_priorities, nodes)


class TestHASerializerPatching(TestNovaOrchestratorHASerializer):

    @property
    def serializer(self):
        self.cluster_mock.pending_release_id = '111'
        with mock.patch(
                'nailgun.objects.release.extract_env_version',
                return_value='5.0'):
            return DeploymentHASerializer(AstuteGraph(self.cluster_mock))

    def test_set_deployment_priorities(self):
        nodes = [
            {'role': 'zabbix-server'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'primary-controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'ceph-osd'}
        ]
        self.add_default_params(nodes)
        self.serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'zabbix-server', 'priority': 100},
            {'role': 'mongo', 'priority': 200},
            {'role': 'primary-mongo', 'priority': 300},
            {'role': 'primary-controller', 'priority': 400},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 600},
            {'role': 'ceph-osd', 'priority': 700}
        ]
        self.add_default_params(expected_priorities)
        self.assertEqual(expected_priorities, nodes)

    def test_set_deployment_priorities_many_cntrls(self):
        nodes = [
            {'role': 'zabbix-server'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'primary-controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'ceph-osd'}
        ]
        self.add_default_params(nodes)
        self.serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'zabbix-server', 'priority': 100},
            {'role': 'mongo', 'priority': 200},
            {'role': 'primary-mongo', 'priority': 300},
            {'role': 'primary-controller', 'priority': 400},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 600},
            {'role': 'controller', 'priority': 700},
            {'role': 'controller', 'priority': 800},
            {'role': 'controller', 'priority': 900},
            {'role': 'controller', 'priority': 1000},
            {'role': 'controller', 'priority': 1100},
            {'role': 'controller', 'priority': 1200},
            {'role': 'ceph-osd', 'priority': 1300}
        ]
        self.add_default_params(expected_priorities)
        self.assertEqual(expected_priorities, nodes)


# TODO(awoodward): multinode deprecation: probably has duplicates
class TestNeutronOrchestratorSerializer(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestNeutronOrchestratorSerializer, self).setUp()
        self.new_env_release_version = None
        self.cluster = self.create_env('ha_compact')
        objects.Cluster.set_primary_roles(self.cluster, self.cluster.nodes)

    def create_env(self, mode, segment_type='vlan'):
        release_kwargs = {}
        if self.new_env_release_version:
            release_kwargs['version'] = self.new_env_release_version
        cluster = self.env.create(
            release_kwargs=release_kwargs,
            cluster_kwargs={
                'mode': mode,
                'net_provider': 'neutron',
                'net_segment_type': segment_type
            },
            nodes_kwargs=[
                {'roles': ['controller', 'cinder'], 'pending_addition': True},
                {'roles': ['compute', 'cinder'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': [], 'pending_roles': ['cinder'],
                 'pending_addition': True}])

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    def serialize_env_w_version(self, version):
        self.new_env_release_version = version
        cluster = self.create_env(mode='ha_compact')
        serializer = get_serializer_for_cluster(cluster)
        return serializer(AstuteGraph(cluster)).serialize(
            cluster, cluster.nodes)

    def assert_roles_flattened(self, nodes):
        self.assertEqual(len(nodes), 6)
        self.assert_nodes_with_role(nodes, 'controller', 1)
        self.assert_nodes_with_role(nodes, 'compute', 2)
        self.assert_nodes_with_role(nodes, 'cinder', 3)

    def set_assign_public_to_all_nodes(self, cluster_db, value):
        attrs = cluster_db.attributes.editable
        attrs['public_network_assignment']['assign_to_all_nodes']['value'] = \
            value
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_db.id}),
            params=jsonutils.dumps({'editable': attrs}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(
            attrs['public_network_assignment']['assign_to_all_nodes']['value'],
            value
        )

    def test_serialize_nodes(self):
        serialized_nodes = self.serializer.serialize_nodes(self.cluster.nodes)
        self.assert_roles_flattened(serialized_nodes)

        # Each not should be same as result of
        # serialize_node function
        for serialized_node in serialized_nodes:
            node_db = self.db.query(Node).get(int(serialized_node['uid']))

            expected_node = self.serializer.serialize_node(
                node_db, serialized_node['role'])
            self.assertEqual(serialized_node, expected_node)

    def test_neutron_vlan_ids_tag_present_on_6_0_env(self):
        serialized_nodes = self.serialize_env_w_version('2014.2-6.0')
        for node in serialized_nodes:
            for item in node['network_scheme']['transformations']:
                if 'tags' in item:
                    self.assertEqual(item['tags'], item['vlan_ids'])

    def check_5x_60_neutron_attrs(self, version):
        serialized_nodes = self.serialize_env_w_version(version)
        for node in serialized_nodes:
            self.assertEqual(
                {
                    "network_type": "local",
                    "segment_id": None,
                    "router_ext": True,
                    "physnet": None
                },
                node['quantum_settings']['predefined_networks'][
                    'net04_ext']['L2']
            )
            self.assertFalse(
                'physnet1' in node['quantum_settings']['L2']['phys_nets']
            )

    def test_serialize_neutron_attrs_on_6_0_env(self):
        self.check_5x_60_neutron_attrs("2014.2-6.0")

    def test_serialize_neutron_attrs_on_5_1_env(self):
        self.check_5x_60_neutron_attrs("2014.1.1-5.1")

    def check_50x_neutron_attrs(self, version):
        serialized_nodes = self.serialize_env_w_version(version)
        for node in serialized_nodes:
            self.assertEqual(
                {
                    "network_type": "flat",
                    "segment_id": None,
                    "router_ext": True,
                    "physnet": "physnet1"
                },
                node['quantum_settings']['predefined_networks'][
                    'net04_ext']['L2']
            )
            self.assertEqual(
                {
                    "bridge": "br-ex",
                    "vlan_range": None
                },
                node['quantum_settings']['L2']['phys_nets']['physnet1']
            )

    def test_serialize_neutron_attrs_on_5_0_2_env(self):
        self.check_50x_neutron_attrs("2014.1.1-5.0.2")

    def test_serialize_neutron_attrs_on_5_0_1_env(self):
        self.check_50x_neutron_attrs("2014.1.1-5.0.1")

    def test_serialize_neutron_attrs_on_5_0_env(self):
        self.check_50x_neutron_attrs("2014.1")

    def test_serialize_node(self):
        node = self.env.create_node(
            api=True, cluster_id=self.cluster.id, pending_addition=True)
        objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)

        node_db = self.db.query(Node).get(node['id'])
        serialized_data = self.serializer.serialize_node(node_db, 'controller')

        self.assertEqual(serialized_data['role'], 'controller')
        self.assertEqual(serialized_data['uid'], str(node_db.id))
        self.assertEqual(serialized_data['status'], node_db.status)
        self.assertEqual(serialized_data['online'], node_db.online)
        self.assertEqual(serialized_data['fqdn'],
                         'node-%d.%s' % (node_db.id, settings.DNS_DOMAIN))

    def test_node_list(self):
        assign_public_options = (False, True)
        for assign in assign_public_options:
            self.set_assign_public_to_all_nodes(self.cluster, assign)

            # Clear IPs
            for ip in self.db.query(models.IPAddr):
                self.db.delete(ip)
            self.db.flush()

            objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)
            node_list = self.serializer.get_common_attrs(self.cluster)['nodes']

            roles_w_public_count = 0

            # Check right nodes count with right roles
            self.assert_roles_flattened(node_list)

            # Check common attrs
            for node in node_list:
                node_db = self.db.query(Node).get(int(node['uid']))
                is_public = objects.Node.should_have_public(node_db)
                if is_public:
                    self.assertEqual(node['public_netmask'], '255.255.255.0')
                    roles_w_public_count += 1
                else:
                    self.assertFalse('public_netmask' in node)
                self.assertEqual(node['internal_netmask'], '255.255.255.0')
                self.assertEqual(node['storage_netmask'], '255.255.255.0')
                self.assertEqual(node['uid'], str(node_db.id))
                self.assertEqual(node['name'], 'node-%d' % node_db.id)
                self.assertEqual(
                    node['fqdn'],
                    'node-%d.%s' % (node_db.id, settings.DNS_DOMAIN))

            # We have 6 roles on 4 nodes summarily.
            # Only 1 node w 2 roles (controller+cinder) will have public
            # when 'assign_to_all_nodes' option is switched off
            self.assertEqual(roles_w_public_count, 6 if assign else 2)

            # Check uncommon attrs
            node_uids = sorted(set([int(n['uid']) for n in node_list]))
            man_ip = [str(ip) for ip in IPRange('192.168.0.1', '192.168.0.4')]
            pub_ip = [str(ip) for ip in IPRange('172.16.0.2', '172.16.0.5')]
            sto_ip = [str(ip) for ip in IPRange('192.168.1.1', '192.168.1.4')]
            expected_list = [
                {'roles': ['controller', 'cinder']},
                {'roles': ['compute', 'cinder']},
                {'roles': ['compute']},
                {'roles': ['cinder']}]
            for i in range(len(expected_list)):
                expected_list[i]['attrs'] = {'uid': str(node_uids[i])}
                if assign:
                    expected_list[i]['attrs']['public_address'] = pub_ip[i]
            if not assign:
                expected_list[0]['attrs']['public_address'] = pub_ip[0]

            # Check if ips are unique for node and
            # they are the same for all nodes roles
            used_man_ip, used_pub_ip, used_sto_ip = [], [], []
            for expected in expected_list:
                attrs = expected['attrs']

                ref_node = self.filter_by_uid(node_list, attrs['uid'])[0]
                is_public = objects.Node.should_have_public(
                    objects.Node.get_by_mac_or_uid(node_uid=attrs['uid']))
                self.assertTrue(ref_node['internal_address'] in man_ip)
                self.assertTrue(ref_node['storage_address'] in sto_ip)
                self.assertFalse(ref_node['internal_address'] in used_man_ip)
                self.assertFalse(ref_node['storage_address'] in used_sto_ip)
                used_man_ip.append(ref_node['internal_address'])
                used_sto_ip.append(ref_node['storage_address'])
                # Check if pubclic ip field exists
                if is_public:
                    self.assertTrue(ref_node['public_address'] in pub_ip)
                    self.assertFalse(ref_node['public_address'] in used_pub_ip)
                    used_pub_ip.append(ref_node['public_address'])

                for role in expected['roles']:
                    nodes = self.filter_by_role(node_list, role)
                    node = self.filter_by_uid(nodes, attrs['uid'])[0]
                    if is_public:
                        self.assertEqual(node['public_address'],
                                         ref_node['public_address'])
                    else:
                        self.assertFalse('public_address' in node)
                    self.assertEqual(node['storage_address'],
                                     ref_node['storage_address'])
                    self.assertEqual(node['internal_address'],
                                     ref_node['internal_address'])

    def test_public_serialization_for_different_roles(self):
        assign_public_options = (False, True)
        for assign in assign_public_options:
            self.set_assign_public_to_all_nodes(self.cluster, assign)

            objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)
            serialized_nodes = self.serializer.serialize(self.cluster,
                                                         self.cluster.nodes)
            need_public_nodes_count = set()
            for node in serialized_nodes:
                node_db = self.db.query(Node).get(int(node['uid']))
                is_public = objects.Node.should_have_public(node_db)
                if is_public:
                    need_public_nodes_count.add(int(node['uid']))

                net_man = objects.Node.get_network_manager(node_db)
                self.assertEqual(
                    net_man._get_ip_by_network_name(
                        node_db, 'public') is not None,
                    is_public
                )

                for node_attrs in node['nodes']:
                    is_public_for_role = objects.Node.should_have_public(
                        objects.Node.get_by_mac_or_uid(
                            node_uid=int(node_attrs['uid'])))
                    self.assertEqual('public_address' in node_attrs,
                                     is_public_for_role)
                    self.assertEqual('public_netmask' in node_attrs,
                                     is_public_for_role)

                self.assertEqual(
                    {
                        'action': 'add-br',
                        'name': 'br-ex'
                    } in node['network_scheme']['transformations'],
                    is_public
                )
                self.assertEqual(
                    {
                        'action': 'add-patch',
                        'bridges': ['br-eth0', 'br-ex'],
                        'trunks': [0]
                    } in node['network_scheme']['transformations'],
                    is_public
                )
                self.assertEqual(
                    'ex' in node['network_scheme']['roles'],
                    is_public
                )
                self.assertEqual(
                    'br-ex' in node['network_scheme']['endpoints'],
                    is_public
                )

            self.assertEqual(len(need_public_nodes_count), 4 if assign else 1)

    def test_neutron_l3_gateway(self):
        cluster = self.create_env('ha_compact', 'gre')
        test_gateway = "192.168.111.255"
        public_ng = self.db.query(NetworkGroup).filter(
            NetworkGroup.name == 'public'
        ).filter(
            NetworkGroup.group_id ==
            objects.Cluster.get_default_group(cluster).id
        ).first()
        public_ng.gateway = test_gateway
        self.db.add(public_ng)
        self.db.commit()

        facts = self.serializer.serialize(cluster, cluster.nodes)

        pd_nets = facts[0]["quantum_settings"]["predefined_networks"]
        self.assertEqual(
            pd_nets["net04_ext"]["L3"]["gateway"],
            test_gateway
        )

    def test_gre_segmentation(self):
        cluster = self.create_env('ha_compact', 'gre')
        facts = self.serializer.serialize(cluster, cluster.nodes)

        for fact in facts:
            self.assertEqual(
                fact['quantum_settings']['L2']['segmentation_type'], 'gre')
            self.assertEqual(
                'br-prv' in fact['network_scheme']['endpoints'], False)
            self.assertEqual(
                'private' in (fact['network_scheme']['roles']), False)

    def test_gw_added_but_default_gw_is_ex_or_admin(self):
        self.new_env_release_version = '2014.2.-6.0'
        cluster = self.create_env('ha_compact', 'gre')

        networks = objects.Cluster.get_default_group(cluster).networks
        for net in networks:
            if net.name in ('storage', 'management'):
                net.gateway = str(IPNetwork(net["cidr"]).cidr[1])
        self.db.flush()

        objects.NodeCollection.prepare_for_deployment(cluster.nodes)
        serializer = get_serializer_for_cluster(cluster)(AstuteGraph(cluster))
        facts = serializer.serialize(cluster, cluster.nodes)

        for fact in facts:
            ep = fact['network_scheme']['endpoints']
            if 'br-ex' in ep:
                self.assertNotIn('default_gateway', ep['br-fw-admin'])
                self.assertIn('gateway', ep['br-ex'])
                self.assertIn('default_gateway', ep['br-ex'])
                self.assertTrue(ep['br-ex']['default_gateway'])
            else:
                self.assertIn('gateway', ep['br-fw-admin'])
                self.assertIn('default_gateway', ep['br-fw-admin'])
                self.assertTrue(ep['br-fw-admin']['default_gateway'])
            self.assertIn('gateway', ep['br-storage'])
            self.assertIn('gateway', ep['br-mgmt'])

    def _create_cluster_for_vlan_splinters(self, segment_type='gre'):
        meta = {
            'interfaces': [
                {'name': 'eth0', 'mac': self.env.generate_random_mac()},
                {'name': 'eth1', 'mac': self.env.generate_random_mac()},
                {'name': 'eth2', 'mac': self.env.generate_random_mac()},
                {'name': 'eth3', 'mac': self.env.generate_random_mac()},
                {'name': 'eth4', 'mac': self.env.generate_random_mac()}
            ]
        }
        cluster = self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': segment_type
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True,
                 'meta': meta}
            ]
        )

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    def test_vlan_splinters_disabled(self):
        cluster = self._create_cluster_for_vlan_splinters()
        cluster_id = cluster.id
        editable_attrs = self._make_data_copy(cluster.attributes.editable)

        # Remove 'vlan_splinters' attribute and check results.

        editable_attrs.pop('vlan_splinters', None)
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        cluster = self.db.query(Cluster).get(cluster_id)
        self.assertNotIn('vlan_splinters', editable_attrs)

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertIn('vlan_splinters', L2_attrs)
            self.assertEqual(L2_attrs['vlan_splinters'], 'off')
            self.assertNotIn('trunks', L2_attrs)

        # Set 'vlan_splinters' to 'some_text' and check results.

        editable_attrs = self._make_data_copy(cluster.attributes.editable)
        editable_attrs['vlan_splinters'] = {'vswitch': {'value': 'some_text'}}
        editable_attrs['vlan_splinters']['metadata'] = {'enabled': True}
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        cluster = self.db.query(Cluster).get(cluster_id)
        editable_attrs = cluster.attributes.editable
        self.assertEqual(editable_attrs['vlan_splinters']['vswitch']['value'],
                         'some_text')

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertNotIn('vlan_splinters', L2_attrs)
            self.assertNotIn('trunks', L2_attrs)

        # Set 'vlan_splinters' to 'disabled' and check results.

        editable_attrs['vlan_splinters']['metadata']['enabled'] = False
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        cluster = self.db.query(Cluster).get(cluster_id)
        editable_attrs = cluster.attributes.editable
        self.assertEqual(
            editable_attrs['vlan_splinters']['metadata']['enabled'],
            False
        )

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertIn('vlan_splinters', L2_attrs)
            self.assertEqual(L2_attrs['vlan_splinters'], 'off')
            self.assertNotIn('trunks', L2_attrs)

    def test_kernel_lt_vlan_splinters(self):
        cluster = self._create_cluster_for_vlan_splinters()
        cluster_id = cluster.id
        editable_attrs = self._make_data_copy(cluster.attributes.editable)

        # value of kernel-ml should end up with vlan_splinters = off
        editable_attrs['vlan_splinters']['metadata']['enabled'] = True
        editable_attrs['vlan_splinters']['vswitch']['value'] = 'kernel_lt'
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        cluster = self.db.query(Cluster).get(cluster_id)
        editable_attrs = cluster.attributes.editable
        self.assertEqual(editable_attrs['vlan_splinters']['vswitch']['value'],
                         'kernel_lt')

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertIn('vlan_splinters', L2_attrs)
            self.assertEqual(L2_attrs['vlan_splinters'], 'off')
            self.assertNotIn('trunks', L2_attrs)

    def test_hard_vlan_splinters_in_gre(self):
        cluster = self._create_cluster_for_vlan_splinters('gre')
        editable_attrs = self._make_data_copy(cluster.attributes.editable)

        editable_attrs['vlan_splinters']['metadata']['enabled'] = True
        editable_attrs['vlan_splinters']['vswitch']['value'] = 'hard'
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        vlan_set = set(
            [ng.vlan_start for ng in cluster.network_groups if ng.vlan_start]
        )
        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertIn('vlan_splinters', L2_attrs)
            self.assertEqual(L2_attrs['vlan_splinters'], 'auto')
            self.assertIn('trunks', L2_attrs)
            self.assertIn(0, L2_attrs['trunks'])
            map(
                lambda n: vlan_set.remove(n) if n else None,
                L2_attrs['trunks']
            )
        self.assertEqual(len(vlan_set), 0)

    def test_hard_vlan_splinters_in_vlan(self):
        cluster = self._create_cluster_for_vlan_splinters('vlan')
        editable_attrs = self._make_data_copy(cluster.attributes.editable)

        editable_attrs['vlan_splinters']['metadata']['enabled'] = True
        editable_attrs['vlan_splinters']['vswitch']['value'] = 'hard'
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        vlan_set = set(
            [ng.vlan_start for ng in cluster.network_groups if ng.vlan_start]
        )
        private_vlan_range = cluster.network_config["vlan_range"]
        vlan_set.update(xrange(*private_vlan_range))
        vlan_set.add(private_vlan_range[1])

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertIn('vlan_splinters', L2_attrs)
            self.assertEqual(L2_attrs['vlan_splinters'], 'auto')
            self.assertIn('trunks', L2_attrs)
            self.assertIn(0, L2_attrs['trunks'])
            map(
                lambda n: vlan_set.remove(n) if n else None,
                L2_attrs['trunks']
            )
        self.assertEqual(len(vlan_set), 0)

    def test_soft_vlan_splinters_in_vlan(self):
        cluster = self._create_cluster_for_vlan_splinters('vlan')
        editable_attrs = self._make_data_copy(cluster.attributes.editable)

        editable_attrs['vlan_splinters']['metadata']['enabled'] = True
        editable_attrs['vlan_splinters']['vswitch']['value'] = 'soft'
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertIn('vlan_splinters', L2_attrs)
            self.assertEqual(L2_attrs['vlan_splinters'], 'auto')
            self.assertIn('trunks', L2_attrs)
            self.assertEqual(L2_attrs['trunks'], [0])


class TestNeutronOrchestratorHASerializer(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestNeutronOrchestratorHASerializer, self).setUp()
        self.cluster = self.create_env('ha_compact')
        objects.Cluster.set_primary_roles(self.cluster, self.cluster.nodes)

    def create_env(self, mode):
        cluster = self.env.create(
            cluster_kwargs={
                'mode': mode,
                'net_provider': 'neutron',
                'net_segment_type': 'vlan'
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller', 'cinder'], 'pending_addition': True},
                {'roles': ['compute', 'cinder'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}
            ]
        )

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    @property
    def serializer(self):
        with mock.patch(
                'nailgun.objects.release.extract_env_version',
                return_value='5.0'):
            return DeploymentHASerializer(AstuteGraph(self.cluster_mock))

    def test_node_list(self):
        serialized_nodes = self.serializer.node_list(self.cluster.nodes)

        for node in serialized_nodes:
            # Each node has swift_zone
            self.assertEqual(node['swift_zone'], node['uid'])

    def test_get_common_attrs(self):
        attrs = self.serializer.get_common_attrs(self.cluster)
        # vips
        self.assertEqual(attrs['management_vip'], '192.168.0.7')
        self.assertTrue(
            re.compile('172.16.0.[1-9]').match(attrs['public_vip']))

        # last_contrller
        controllers = self.get_controllers(self.cluster.id)
        self.assertEqual(attrs['last_controller'],
                         'node-%d' % controllers[-1].id)

        # primary_controller
        controllers = self.filter_by_role(attrs['nodes'], 'primary-controller')
        self.assertEqual(controllers[0]['role'], 'primary-controller')

        # mountpoints and mp attrs
        self.assertEqual(
            attrs['mp'],
            [{'point': '1', 'weight': '1'},
             {'point': '2', 'weight': '2'}])


class TestNeutronOrchestratorSerializerBonds(OrchestratorSerializerTestBase):

    def create_env(self, nodes_count=2, nic_count=3, segment_type='vlan'):
        cluster = self.env.create_cluster(
            net_provider='neutron',
            net_segment_type=segment_type)
        self.env.create_nodes_w_interfaces_count(
            nodes_count=1,
            if_count=nic_count,
            roles=['controller', 'cinder'],
            pending_addition=True,
            cluster_id=cluster['id'])
        self.env.create_nodes_w_interfaces_count(
            nodes_count=nodes_count - 1,
            if_count=nic_count,
            roles=['compute'],
            pending_addition=True,
            cluster_id=cluster['id'])
        cluster_db = self.db.query(Cluster).get(cluster['id'])
        return cluster_db

    def check_add_bond_msg_lacp(self, msg):
        self.assertEqual(
            msg,
            {
                'action': 'add-bond',
                'bridge': 'br-ovsbond0',
                'interfaces': ['eth1', 'eth2'],
                'name': 'ovsbond0',
                'properties': ['lacp=active', 'bond_mode=balance-tcp']
            })

    def check_add_bond_msg_non_lacp(self, msg, mode):
        self.assertEqual(
            msg,
            {
                'action': 'add-bond',
                'bridge': 'br-ovsbond0',
                'interfaces': ['eth1', 'eth2'],
                'name': 'ovsbond0',
                'properties': ['bond_mode={0}'.format(mode)]
            })

    def check_bond_with_mode(self, mode):
        cluster = self.create_env()
        for node in cluster.nodes:
            self.env.make_bond_via_api('ovsbond0',
                                       mode,
                                       ['eth1', 'eth2'],
                                       node.id)
        facts = self.serialize(cluster)
        for node in facts:
            transforms = node['network_scheme']['transformations']
            bonds = filter(lambda t: t['action'] == 'add-bond',
                           transforms)
            self.assertEqual(len(bonds), 1)
            if mode == consts.BOND_MODES.lacp_balance_tcp:
                self.check_add_bond_msg_lacp(bonds[0])
            else:
                self.check_add_bond_msg_non_lacp(bonds[0], mode)

    def test_bonds_serialization(self):
        for mode in consts.BOND_MODES:
            self.check_bond_with_mode(mode)


class TestCephOsdImageOrchestratorSerialize(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestCephOsdImageOrchestratorSerialize, self).setUp()
        cluster = self.env.create(
            cluster_kwargs={
                'mode': 'multinode'},
            nodes_kwargs=[
                {'roles': ['controller', 'ceph-osd']}])
        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {'storage': {'images_ceph': {'value': True}}}}),
            headers=self.default_headers)
        self.cluster = self.db.query(Cluster).get(cluster['id'])

    def test_glance_image_cache_max_size(self):
        data = self.serialize(self.cluster)
        self.assertEqual(len(data), 2)
        # one node - 2 roles
        self.assertEqual(data[0]['uid'], data[1]['uid'])
        self.assertEqual(data[0]['glance']['image_cache_max_size'], '0')
        self.assertEqual(data[1]['glance']['image_cache_max_size'], '0')


class TestCephPgNumOrchestratorSerialize(OrchestratorSerializerTestBase):

    def create_env(self, nodes, osd_pool_size='2'):
        cluster = self.env.create(
            cluster_kwargs={
                'mode': 'multinode'},
            nodes_kwargs=nodes)
        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps(
                {'editable': {
                    'storage': {
                        'osd_pool_size': {'value': osd_pool_size}}}}),
            headers=self.default_headers)
        return self.db.query(Cluster).get(cluster['id'])

    def test_pg_num_no_osd_nodes(self):
        cluster = self.create_env([
            {'roles': ['controller']}])
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 128)

    def test_pg_num_1_osd_node(self):
        cluster = self.create_env([
            {'roles': ['controller', 'ceph-osd']}])
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 256)

    def test_pg_num_1_osd_node_repl_4(self):
        cluster = self.create_env(
            [{'roles': ['controller', 'ceph-osd']}],
            '4')
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 128)

    def test_pg_num_3_osd_nodes(self):
        cluster = self.create_env([
            {'roles': ['controller', 'ceph-osd']},
            {'roles': ['compute', 'ceph-osd']},
            {'roles': ['compute', 'ceph-osd']}])
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 512)


class TestMongoNodesSerialization(OrchestratorSerializerTestBase):

    def create_env(self):
        cluster = self.env.create(
            cluster_kwargs={
                'mode': 'ha_compact',
                'network_manager': 'FlatDHCPManager'
            },
            nodes_kwargs=[
                {'roles': ['mongo'], 'pending_addition': True},
                {'roles': ['mongo'], 'pending_addition': True},
                {'roles': ['mongo'], 'pending_addition': True}
            ]
        )
        cluster = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster.nodes)
        return cluster

    @property
    def serializer_ha(self):
        with mock.patch(
                'nailgun.objects.release.extract_env_version',
                return_value='5.0'):
            return DeploymentHASerializer(AstuteGraph(
                self.cluster_mock))

    @property
    def serializer_mn(self):
        with mock.patch(
                'nailgun.objects.release.extract_env_version',
                return_value='5.0'):
            return DeploymentMultinodeSerializer(
                AstuteGraph(self.cluster_mock))

    def test_mongo_roles_equals_in_defferent_modes(self):
        cluster = self.create_env()
        ha_nodes = self.serializer_ha.serialize_nodes(cluster.nodes)
        mn_nodes = self.serializer_mn.serialize_nodes(cluster.nodes)
        self.assertEqual(mn_nodes, ha_nodes)

    def test_primary_node_selected(self):
        cluster = self.create_env()
        ha_nodes = self.serializer_ha.serialize_nodes(cluster.nodes)
        mn_nodes = self.serializer_mn.serialize_nodes(cluster.nodes)

        def primary_nodes_count(nodes):
            return len(filter(lambda x: x['role'] == 'primary-mongo', nodes))

        self.assertEqual(1, primary_nodes_count(ha_nodes))
        self.assertEqual(1, primary_nodes_count(mn_nodes))


class TestNSXOrchestratorSerializer(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestNSXOrchestratorSerializer, self).setUp()
        self.cluster = self.create_env('ha_compact')

    def create_env(self, mode, segment_type='gre'):
        cluster = self.env.create(
            cluster_kwargs={
                'mode': mode,
                'net_provider': 'neutron',
                'net_segment_type': segment_type
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
            ]
        )

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        editable_attrs = self._make_data_copy(cluster_db.attributes.editable)
        nsx_attrs = editable_attrs.setdefault('nsx_plugin', {})
        nsx_attrs.setdefault('metadata', {})['enabled'] = True
        cluster_db.attributes.editable = editable_attrs

        self.db.commit()
        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    def test_serialize_node(self):
        serialized_data = self.serializer.serialize(self.cluster,
                                                    self.cluster.nodes)[0]

        q_settings = serialized_data['quantum_settings']
        self.assertIn('L2', q_settings)
        self.assertIn('provider', q_settings['L2'])
        self.assertEqual(q_settings['L2']['provider'], 'nsx')
        l3_settings = q_settings['L3']
        self.assertIn('dhcp_agent', l3_settings)
        self.assertIn('enable_isolated_metadata', l3_settings['dhcp_agent'])
        self.assertEqual(l3_settings['dhcp_agent']['enable_isolated_metadata'],
                         True)
        self.assertIn('enable_metadata_network', l3_settings['dhcp_agent'])
        self.assertEqual(l3_settings['dhcp_agent']['enable_metadata_network'],
                         True)


class BaseDeploymentSerializer(BaseIntegrationTest):

    node_name = 'node name'
    # Needs to be set in childs
    serializer = None

    def create_env(self, mode):
        return self.env.create(
            cluster_kwargs={
                'mode': mode,
                'net_provider': 'neutron',
                'net_segment_type': 'gre'},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'pending_addition': True,
                 'name': self.node_name,
                 }
            ])

    def check_serialize_node(self):
        self.assertEqual(
            self.serializer.serialize_node(
                self.env.nodes[0], 'role')['user_node_name'],
            self.node_name)

    def check_serialize_node_for_node_list(self):
        self.assertEqual(
            self.serializer.serialize_node_for_node_list(
                self.env.nodes[0], 'role')['user_node_name'],
            self.node_name)

    def check_generate_test_vm_image_data(self):
        img_name = 'TestVM-VMDK'
        disk_format = 'vmdk'
        img_path = '/opt/vm/cirros-i386-disk.vmdk'

        self.assertEqual(
            len(self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image']), 2)

        self.assertEqual(
            self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image'][0]['img_name'],
            img_name)

        self.assertEqual(
            self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image'][0]['disk_format'],
            disk_format)

        self.assertEqual(
            self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image'][0]['img_path'],
            img_path)

    def check_generate_vmware_attributes_data(self):
        cluster_db = self.db.query(Cluster).get(self.cluster['id'])
        cluster_attrs = objects.Cluster.get_attributes(cluster_db).editable
        cluster_attrs.get('common', {}).setdefault('use_vcenter', {})
        cluster_attrs['common']['use_vcenter']['value'] = True

        objects.Cluster.update_attributes(
            cluster_db, {'editable': cluster_attrs})
        setattr(
            cluster_db.vmware_attributes,
            'editable',
            self.vm_data[0]['editable'])
        self.db.flush()

        result = self.serializer.serialize_node(
            self.env.nodes[0], 'controller')

        self.assertEqual(len(result['vcenter']['computes']), 2)

        self.assertIn(
            result['vcenter']['computes'][0]['service_name'],
            ['Compute 1', 'Compute 3'])

        self.assertIn(
            result['vcenter']['computes'][1]['service_name'],
            ['Compute 1', 'Compute 3'])

        # check compute parameters
        self.assertEqual(
            result['vcenter']['computes'][0]['availability_zone_name'],
            "Zone 1")
        self.assertEqual(
            result['vcenter']['computes'][0]['vc_host'],
            "1.2.3.4")
        self.assertEqual(
            result['vcenter']['computes'][0]['vc_user'],
            "admin")
        self.assertEqual(
            result['vcenter']['computes'][0]['vc_password'],
            "secret")
        self.assertEqual(
            result['vcenter']['computes'][0]['vc_cluster'],
            "cluster1")

        self.assertTrue(result['use_vcenter'])
        self.assertEqual(result['vcenter']['esxi_vlan_interface'], "eth0")

        # check cinder parameters
        self.assertEqual(
            result['cinder']['instances'][0]['availability_zone_name'],
            "Zone 1")
        self.assertEqual(
            result['cinder']['instances'][0]['vc_host'],
            "1.2.3.4")
        self.assertEqual(
            result['cinder']['instances'][0]['vc_user'],
            "admin")
        self.assertEqual(
            result['cinder']['instances'][0]['vc_password'],
            "secret")

        # check glance parameters
        self.assertEqual(result['glance']['vc_host'], "1.2.3.4")
        self.assertEqual(result['glance']['vc_user'], "admin")
        self.assertEqual(result['glance']['vc_password'], "secret")

    def check_no_murano_data(self):
        glance_properties = self.serializer.generate_test_vm_image_data(
            self.env.nodes[0])['test_vm_image']['glance_properties']
        self.assertNotIn('murano_image_info', glance_properties)

    def check_murano_data(self):
        glance_properties = self.serializer.generate_test_vm_image_data(
            self.env.nodes[0])['test_vm_image']['glance_properties']
        self.assertIn('murano_image_info', glance_properties)


class TestDeploymentMultinodeSerializer61(BaseDeploymentSerializer):

    def setUp(self):
        super(TestDeploymentMultinodeSerializer61, self).setUp()
        self.cluster = self.create_env('multinode')
        objects.NodeCollection.prepare_for_deployment(self.env.nodes)
        self.serializer = DeploymentMultinodeSerializer61(self.cluster)
        self.vm_data = self.env.read_fixtures(['vmware_attributes'])

    def test_serialize_node(self):
        self.check_serialize_node()

    def test_serialize_node_for_node_list(self):
        self.check_serialize_node_for_node_list()

    def test_generate_vmware_attributes_data(self):
        self.check_generate_vmware_attributes_data()

    def test_glance_properties(self):
        self.check_no_murano_data()


class TestDeploymentAttributesSerialization61(BaseDeploymentSerializer):

    def setUp(self):
        super(TestDeploymentAttributesSerialization61, self).setUp()
        self.cluster = self.create_env('ha_compact')
        objects.NodeCollection.prepare_for_deployment(self.env.nodes)
        self.serializer = DeploymentHASerializer61(self.cluster)

    def test_serialize_workloads_collector_user(self):
        oswl_user = self.serializer.get_common_attrs(
            self.env.clusters[0]
        )['workloads_collector']
        self.assertEqual(set(oswl_user.keys()),
                         set(['username',
                              'enabled',
                              'password',
                              'metadata',
                              'tenant']))
        self.assertEqual(oswl_user['username'], 'workloads_collector')
        self.assertEqual(oswl_user['enabled'], True)
        self.assertEqual(len(oswl_user['password']), 8)
        self.assertEqual(oswl_user['tenant'], 'services')


class TestDeploymentHASerializer61(BaseDeploymentSerializer):

    def setUp(self):
        super(TestDeploymentHASerializer61, self).setUp()
        self.cluster = self.create_env('ha_compact')
        objects.NodeCollection.prepare_for_deployment(self.env.nodes)
        self.serializer = DeploymentHASerializer61(self.cluster)
        self.vm_data = self.env.read_fixtures(['vmware_attributes'])

    def check_generate_test_vm_image_data(self):
        kvm_img_name = 'TestVM'
        kvm_img_disk_format = 'qcow2'
        kvm_img_path = '/opt/vm/cirros-x86_64-disk.img'
        vmdk_img_name = 'TestVM-VMDK'
        vmdk_disk_format = 'vmdk'
        vmdk_img_path = '/opt/vm/cirros-i386-disk.vmdk'

        self.assertEqual(
            len(self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image']), 2)

        self.assertEqual(
            self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image'][0]['img_name'],
            vmdk_img_name)

        self.assertEqual(
            self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image'][0]['disk_format'],
            vmdk_disk_format)

        self.assertEqual(
            self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image'][0]['img_path'],
            vmdk_img_path)

        self.assertEqual(
            self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image'][1]['img_name'],
            kvm_img_name)

        self.assertEqual(
            self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image'][1]['disk_format'],
            kvm_img_disk_format)

        self.assertEqual(
            self.serializer.generate_test_vm_image_data(
                self.env.nodes[0])['test_vm_image'][1]['img_path'],
            kvm_img_path)

    def test_serialize_node(self):
        self.check_serialize_node()

    def test_serialize_node_for_node_list(self):
        self.check_serialize_node_for_node_list()

    def test_generate_test_vm_image_data(self):
        cluster_db = self.db.query(Cluster).get(self.cluster['id'])
        cluster_attrs = objects.Cluster.get_attributes(cluster_db).editable
        cluster_attrs['common'].setdefault('use_vcenter', {})
        cluster_attrs['common']['use_vcenter']['value'] = True

        objects.Cluster.update_attributes(
            cluster_db, {'editable': cluster_attrs})
        self.check_generate_test_vm_image_data()

    def test_generate_vmware_attributes_data(self):
        self.check_generate_vmware_attributes_data()

    def test_glance_properties(self):
        self.check_no_murano_data()


class TestSerializeInterfaceDriversData(BaseIntegrationTest):

    def setUp(self):
        super(TestSerializeInterfaceDriversData, self).setUp()

    def _create_cluster_for_interfaces(self, driver_mapping={},
                                       bus_mapping={},
                                       segment_type='gre'):
        meta = {
            'interfaces': [
                {'name': 'eth0', 'mac': self.env.generate_random_mac(),
                 'driver': driver_mapping.get('eth0', 'igb'),
                 'bus_info': bus_mapping.get('eth0', '0000:05:00.0')},
                {'name': 'eth1', 'mac': self.env.generate_random_mac(),
                 'driver': driver_mapping.get('eth1', 'mlx4_en'),
                 'bus_info': bus_mapping.get('eth1', '0000:06:00.0')}
            ]
        }
        cluster = self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': segment_type
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True,
                 'meta': meta}
            ]
        )

        self.serializer = DeploymentHASerializer61(cluster)
        cluster_db = self.db.query(Cluster).get(cluster['id'])
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    def test_interface_driver_bus_info(self):
        driver_mapping = {'eth0': 'igb',
                          'eth1': 'eth_ipoib'}
        bus_mapping = {'eth0': '0000:01:00.0',
                       'eth1': 'ib1'}
        cluster = \
            self._create_cluster_for_interfaces(driver_mapping, bus_mapping)
        self.db.commit()
        cluster_db = self.db.query(Cluster).get(cluster['id'])
        node = self.serializer.serialize_node(cluster_db.nodes[0],
                                              'controller')
        interfaces = node['network_scheme']['interfaces']
        for iface, iface_attrs in interfaces.items():
            self.assertIn('vendor_specific', iface_attrs)
            self.assertIn('driver', iface_attrs['vendor_specific'])
            self.assertEqual(iface_attrs['vendor_specific']['driver'],
                             driver_mapping[iface])
            self.assertIn('bus_info', iface_attrs['vendor_specific'])
            self.assertEqual(iface_attrs['vendor_specific']['bus_info'],
                             bus_mapping[iface])

    def test_interface_mapping(self):
        cluster = self._create_cluster_for_interfaces(segment_type='vlan')
        network_group = self.db().query(NetworkGroup)
        public_vlan = randint(0, 4095)
        storage_vlan = randint(0, 4095)
        management_vlan = randint(0, 4095)
        private_vlan_range = [randint(0, 4095), randint(0, 4095)]
        vlan_mapping = {'ex': public_vlan,
                        'storage': storage_vlan,
                        'management': management_vlan,
                        'neutron/private': "%s:%s" % (private_vlan_range[0],
                                                      private_vlan_range[1])}
        cluster.network_config["vlan_range"] = private_vlan_range
        network_group.filter_by(name="storage").update(
            {"vlan_start": storage_vlan}, synchronize_session="fetch")
        network_group.filter_by(name="management").update(
            {"vlan_start": management_vlan}, synchronize_session="fetch")
        network_group.filter_by(name="public").update(
            {"vlan_start": public_vlan}, synchronize_session="fetch")
        self.db.commit()

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        node = self.serializer.serialize_node(cluster_db.nodes[0],
                                              'controller')
        endpoints = node['network_scheme']['endpoints']
        net_roles = node['network_scheme']['roles']
        for net_role, bridge in net_roles.items():
            ep_dict = endpoints[bridge]
            if net_role in vlan_mapping.keys():
                self.assertIn('vendor_specific', ep_dict.keys())
                self.assertIn('phy_interfaces',
                              ep_dict['vendor_specific'].keys())
                self.assertIn('vlans', ep_dict['vendor_specific'].keys())
                self.assertEqual(ep_dict['vendor_specific']['vlans'],
                                 vlan_mapping[net_role])


class TestDeploymentHASerializer50(BaseDeploymentSerializer):

    def setUp(self):
        super(TestDeploymentHASerializer50, self).setUp()
        self.cluster = self.create_env('ha_compact')
        objects.NodeCollection.prepare_for_deployment(self.env.nodes)
        self.serializer = DeploymentHASerializer50(self.cluster)

    def test_glance_properties(self):
        self.check_murano_data()


class TestDeploymentMultinodeSerializer50(BaseDeploymentSerializer):

    def setUp(self):
        super(TestDeploymentMultinodeSerializer50, self).setUp()
        self.cluster = self.create_env('multinode')
        objects.NodeCollection.prepare_for_deployment(self.env.nodes)
        self.serializer = DeploymentMultinodeSerializer50(self.cluster)

    def test_glance_properties(self):
        self.check_murano_data()
