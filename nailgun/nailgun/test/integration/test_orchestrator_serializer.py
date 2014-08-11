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

from netaddr import IPRange

from nailgun.consts import OVS_BOND_MODES
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.openstack.common import jsonutils
from nailgun.orchestrator.deployment_serializers import\
    DeploymentHASerializer
from nailgun.orchestrator.deployment_serializers import\
    DeploymentMultinodeSerializer

from nailgun import objects

from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse
from nailgun.volumes import manager


class OrchestratorSerializerTestBase(BaseIntegrationTest):
    """Class containts helpers."""

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

    @property
    def serializer(self):
        return DeploymentHASerializer

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


# TODO(awoodward): multinode deprecation: probably has duplicates
class TestNovaOrchestratorSerializer(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestNovaOrchestratorSerializer, self).setUp()
        self.cluster = self.create_env('ha_compact')

    def create_env(self, mode, network_manager='FlatDHCPManager'):
        node_args = [
            {'roles': ['controller', 'cinder'], 'pending_addition': True},
            {'roles': ['compute', 'cinder'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True},
            {'roles': ['mongo'], 'pending_addition': True},
            {'roles': [], 'pending_roles': ['cinder'],
             'pending_addition': True}]
        cluster = self.env.create(
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
        node_uids = sorted(set([n['uid'] for n in node_list]))
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
            expected_list[i]['attrs'] = {'uid': node_uids[i],
                                         'internal_address': man_ip[i],
                                         'public_address': pub_ip[i],
                                         'storage_address': sto_ip[i]}

        for expected in expected_list:
            attrs = expected['attrs']

            for role in expected['roles']:
                nodes = self.filter_by_role(node_list, role)
                node = self.filter_by_uid(nodes, attrs['uid'])[0]

                self.assertEqual(attrs['internal_address'],
                                 node['internal_address'])
                self.assertEqual(attrs['public_address'],
                                 node['public_address'])
                self.assertEqual(attrs['storage_address'],
                                 node['storage_address'])

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
                'gateway': '172.16.0.1'
            }
        }
        self.datadiff(expected_interfaces, interfaces)

    def test_set_deployment_priorities(self):
        nodes = [
            {'role': 'mongo'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'controller'},
            {'role': 'ceph-osd'},
            {'role': 'other'}
        ]
        serializer = DeploymentMultinodeSerializer()
        serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'mongo', 'priority': 100},
            {'role': 'mongo', 'priority': 200},
            {'role': 'primary-mongo', 'priority': 300},
            {'role': 'controller', 'priority': 400},
            {'role': 'ceph-osd', 'priority': 500},
            {'role': 'other', 'priority': 500}
        ]
        self.assertEqual(expected_priorities, nodes)

    def test_set_critital_node(self):
        nodes = [
            {'role': 'mongo'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'controller'},
            {'role': 'ceph-osd'},
            {'role': 'other'}
        ]
        serializer = DeploymentMultinodeSerializer()
        serializer.set_critical_nodes(self.cluster, nodes)
        expected_ciritial_roles = [
            {'role': 'mongo', 'fail_if_error': False},
            {'role': 'mongo', 'fail_if_error': False},
            {'role': 'primary-mongo', 'fail_if_error': True},
            {'role': 'controller', 'fail_if_error': True},
            {'role': 'ceph-osd', 'fail_if_error': True},
            {'role': 'other', 'fail_if_error': False}
        ]
        self.assertEqual(expected_ciritial_roles, nodes)


class TestNovaOrchestratorHASerializer(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestNovaOrchestratorHASerializer, self).setUp()
        self.cluster = self.create_env('ha_compact')

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
        return DeploymentHASerializer

    def test_set_deployment_priorities(self):
        nodes = [
            {'role': 'zabbix-server'},
            {'role': 'primary-swift-proxy'},
            {'role': 'swift-proxy'},
            {'role': 'storage'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'primary-controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'ceph-osd'},
            {'role': 'other'}
        ]
        self.serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'zabbix-server', 'priority': 100},
            {'role': 'primary-swift-proxy', 'priority': 200},
            {'role': 'swift-proxy', 'priority': 300},
            {'role': 'storage', 'priority': 400},
            {'role': 'mongo', 'priority': 500},
            {'role': 'primary-mongo', 'priority': 600},
            {'role': 'primary-controller', 'priority': 700},
            {'role': 'controller', 'priority': 800},
            {'role': 'controller', 'priority': 800},
            {'role': 'ceph-osd', 'priority': 900},
            {'role': 'other', 'priority': 900}
        ]
        self.assertEqual(expected_priorities, nodes)

    def test_set_deployment_priorities_many_cntrls(self):
        nodes = [
            {'role': 'zabbix-server'},
            {'role': 'primary-swift-proxy'},
            {'role': 'swift-proxy'},
            {'role': 'storage'},
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
            {'role': 'ceph-osd'},
            {'role': 'other'}
        ]
        self.serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'zabbix-server', 'priority': 100},
            {'role': 'primary-swift-proxy', 'priority': 200},
            {'role': 'swift-proxy', 'priority': 300},
            {'role': 'storage', 'priority': 400},
            {'role': 'mongo', 'priority': 500},
            {'role': 'primary-mongo', 'priority': 600},
            {'role': 'primary-controller', 'priority': 700},
            {'role': 'controller', 'priority': 800},
            {'role': 'controller', 'priority': 800},
            {'role': 'controller', 'priority': 800},
            {'role': 'controller', 'priority': 800},
            {'role': 'controller', 'priority': 800},
            {'role': 'controller', 'priority': 800},
            {'role': 'controller', 'priority': 900},
            {'role': 'controller', 'priority': 900},
            {'role': 'ceph-osd', 'priority': 1000},
            {'role': 'other', 'priority': 1000}
        ]
        self.assertEqual(expected_priorities, nodes)

    def test_set_critital_node(self):
        nodes = [
            {'role': 'zabbix-server'},
            {'role': 'primary-swift-proxy'},
            {'role': 'swift-proxy'},
            {'role': 'storage'},
            {'role': 'mongo'},
            {'role': 'primary-mongo'},
            {'role': 'primary-controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'ceph-osd'},
            {'role': 'other'}
        ]
        self.serializer.set_critical_nodes(self.cluster, nodes)
        expected_ciritial_roles = [
            {'role': 'zabbix-server', 'fail_if_error': False},
            {'role': 'primary-swift-proxy', 'fail_if_error': True},
            {'role': 'swift-proxy', 'fail_if_error': False},
            {'role': 'storage', 'fail_if_error': False},
            {'role': 'mongo', 'fail_if_error': False},
            {'role': 'primary-mongo', 'fail_if_error': True},
            {'role': 'primary-controller', 'fail_if_error': True},
            {'role': 'controller', 'fail_if_error': False},
            {'role': 'controller', 'fail_if_error': False},
            {'role': 'ceph-osd', 'fail_if_error': True},
            {'role': 'other', 'fail_if_error': False}
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


# TODO(awoodward): multinode deprecation: probably has duplicates
class TestNeutronOrchestratorSerializer(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestNeutronOrchestratorSerializer, self).setUp()
        self.cluster = self.create_env('ha_compact')

    def create_env(self, mode, segment_type='vlan'):
        cluster = self.env.create(
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

    def assert_roles_flattened(self, nodes):
        self.assertEqual(len(nodes), 6)
        self.assert_nodes_with_role(nodes, 'controller', 1)
        self.assert_nodes_with_role(nodes, 'compute', 2)
        self.assert_nodes_with_role(nodes, 'cinder', 3)

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

        node_db = self.db.query(Node).get(node['id'])
        serialized_data = self.serializer.serialize_node(node_db, 'controller')

        self.assertEqual(serialized_data['role'], 'controller')
        self.assertEqual(serialized_data['uid'], str(node_db.id))
        self.assertEqual(serialized_data['status'], node_db.status)
        self.assertEqual(serialized_data['online'], node_db.online)
        self.assertEqual(serialized_data['fqdn'],
                         'node-%d.%s' % (node_db.id, settings.DNS_DOMAIN))

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
        node_uids = sorted(set([n['uid'] for n in node_list]))
        man_ip = [str(ip) for ip in IPRange('192.168.0.1', '192.168.0.4')]
        pub_ip = [str(ip) for ip in IPRange('172.16.0.2', '172.16.0.5')]
        sto_ip = [str(ip) for ip in IPRange('192.168.1.1', '192.168.1.4')]
        expected_list = [
            {'roles': ['controller', 'cinder']},
            {'roles': ['compute', 'cinder']},
            {'roles': ['compute']},
            {'roles': ['cinder']}]
        for i in range(len(expected_list)):
            expected_list[i]['attrs'] = {'uid': node_uids[i],
                                         'internal_address': man_ip[i],
                                         'public_address': pub_ip[i],
                                         'storage_address': sto_ip[i]}

        for expected in expected_list:
            attrs = expected['attrs']

            for role in expected['roles']:
                nodes = self.filter_by_role(node_list, role)
                node = self.filter_by_uid(nodes, attrs['uid'])[0]

                self.assertEqual(attrs['internal_address'],
                                 node['internal_address'])
                self.assertEqual(attrs['public_address'],
                                 node['public_address'])
                self.assertEqual(attrs['storage_address'],
                                 node['storage_address'])

    def test_neutron_l3_gateway(self):
        cluster = self.create_env('ha_compact', 'gre')
        test_gateway = "192.168.111.255"
        public_ng = self.db.query(NetworkGroup).filter(
            NetworkGroup.name == 'public'
        ).filter(
            NetworkGroup.cluster_id == cluster.id
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
        return DeploymentHASerializer

    def test_node_list(self):
        serialized_nodes = self.serializer.node_list(self.cluster.nodes)

        for node in serialized_nodes:
            # Each node has swift_zone
            self.assertEqual(node['swift_zone'], node['uid'])

    def test_get_common_attrs(self):
        attrs = self.serializer.get_common_attrs(self.cluster)
        # vips
        self.assertEqual(attrs['management_vip'], '192.168.0.7')
        self.assertEqual(attrs['public_vip'], '172.16.0.8')

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
            if mode == OVS_BOND_MODES.lacp_balance_tcp:
                self.check_add_bond_msg_lacp(bonds[0])
            else:
                self.check_add_bond_msg_non_lacp(bonds[0], mode)

    def test_bonds_serialization(self):
        for mode in OVS_BOND_MODES:
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

    def test_mongo_roles_equals_in_defferent_modes(self):
        cluster = self.create_env()
        ha_nodes = DeploymentHASerializer.serialize_nodes(cluster.nodes)
        mn_nodes = DeploymentMultinodeSerializer.serialize_nodes(cluster.nodes)
        self.assertEqual(mn_nodes, ha_nodes)

    def test_primary_node_selected(self):
        cluster = self.create_env()
        ha_nodes = DeploymentHASerializer.serialize_nodes(cluster.nodes)
        mn_nodes = DeploymentMultinodeSerializer.serialize_nodes(cluster.nodes)

        def primary_nodes_count(nodes):
            return len(filter(lambda x: x['role'] == 'primary-mongo', nodes))

        self.assertEqual(1, primary_nodes_count(ha_nodes))
        self.assertEqual(1, primary_nodes_count(mn_nodes))


class TestRepoAndPuppetDataSerialization(OrchestratorSerializerTestBase):

    orch_data = {
        "repo_metadata": {
            "nailgun":
            "http://10.20.0.2:8080/centos-5.0/centos/fuelweb/x86_64/"
        },
        "puppet_modules_source":
        "rsync://10.20.0.2/puppet/release/5.0/modules",
        "puppet_manifests_source":
        "rsync://10.20.0.2/puppet/release/5.0/manifests"
    }

    def test_repo_and_puppet_data_w_orch_data(self):
        release_id = self.env.create_release().id

        resp = self.app.put(
            reverse('ReleaseHandler', kwargs={'obj_id': release_id}),
            params=jsonutils.dumps(
                {
                    "orchestrator_data": self.orch_data
                }
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(200, resp.status_code)

        cluster_id = self.env.create(
            cluster_kwargs={
                'release_id': release_id
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}
            ]
        )["id"]

        cluster = self.db.query(Cluster).get(cluster_id)
        objects.NodeCollection.prepare_for_deployment(cluster.nodes)
        facts = self.serializer.serialize(cluster, cluster.nodes)

        self.assertEqual(1, len(facts))
        fact = facts[0]
        self.assertEqual(
            fact['repo_metadata'],
            {
                'nailgun': 'http://10.20.0.2:8080'
                           '/centos-5.0/centos/fuelweb/x86_64/'
            }
        )
        self.assertEqual(
            fact['puppet_modules_source'],
            'rsync://10.20.0.2/puppet/release/5.0/modules'
        )
        self.assertEqual(
            fact['puppet_manifests_source'],
            'rsync://10.20.0.2/puppet/release/5.0/manifests'
        )

    def test_repo_and_puppet_data_wo_orch_data(self):
        release_id = self.env.create_release().id

        cluster_id = self.env.create(
            cluster_kwargs={
                'release_id': release_id
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}
            ]
        )["id"]

        cluster = self.db.query(Cluster).get(cluster_id)
        objects.NodeCollection.prepare_for_deployment(cluster.nodes)
        facts = self.serializer.serialize(cluster, cluster.nodes)

        self.assertEqual(1, len(facts))
        fact = facts[0]
        self.assertEqual(
            fact['repo_metadata'],
            {
                'nailgun': 'http://127.0.0.1:8080/centos/fuelweb/x86_64'
            }
        )
        self.assertEqual(
            fact['puppet_modules_source'],
            'rsync://127.0.0.1:/puppet/modules/'
        )
        self.assertEqual(
            fact['puppet_manifests_source'],
            'rsync://127.0.0.1:/puppet/manifests/'
        )

    def test_orch_data_w_replaced_deployment_info(self):
        replaced_deployment_info = [{'repo_metadata': 'custom_stuff'}]
        release = self.env.create_release()
        self.env.create(
            cluster_kwargs={'release_id': release.id},
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}
            ])
        objects.Release.update_orchestrator_data(release, self.orch_data)
        self.db.flush()
        self.db.refresh(release)
        self.env.nodes[0].replaced_deployment_info = replaced_deployment_info

        facts = self.serializer.serialize(
            self.env.clusters[0], self.env.nodes)
        self.assertEqual(facts[0]['repo_metadata'],
                         self.orch_data['repo_metadata'])
        self.assertEqual(facts[0]['puppet_modules_source'],
                         self.orch_data['puppet_modules_source'])
        self.assertEqual(facts[0]['puppet_manifests_source'],
                         self.orch_data['puppet_manifests_source'])


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
        self.assertIn('server', q_settings)
        self.assertIn('core_plugin', q_settings['server'])
        self.assertEqual(q_settings['server']['core_plugin'], 'vmware')
        l3_settings = q_settings['L3']
        self.assertIn('dhcp_agent', l3_settings)
        self.assertIn('enable_isolated_metadata', l3_settings['dhcp_agent'])
        self.assertEqual(l3_settings['dhcp_agent']['enable_isolated_metadata'],
                         True)
        self.assertIn('enable_metadata_network', l3_settings['dhcp_agent'])
        self.assertEqual(l3_settings['dhcp_agent']['enable_metadata_network'],
                         True)
