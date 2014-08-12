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

from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import IPAddrRange
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.orchestrator.deployment_serializers \
    import DeploymentHASerializer
from nailgun.orchestrator.deployment_serializers \
    import DeploymentMultinodeSerializer
from nailgun.settings import settings
from nailgun.task.helpers import TaskHelper
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse
from nailgun.volumes import manager


class OrchestratorSerializerTestBase(BaseIntegrationTest):
    """Class containts helpers."""

    def filter_by_role(self, nodes, role):
        return filter(lambda node: node['role'] == role, nodes)

    def filter_by_uid(self, nodes, uid):
        return filter(lambda node: node['uid'] == uid, nodes)

    def assert_nodes_with_role(self, nodes, role, count):
        self.assertEquals(len(self.filter_by_role(nodes, role)), count)

    def get_controllers(self, cluster_id):
        return db().query(Node).\
            filter_by(cluster_id=cluster_id,
                      pending_deletion=False).\
            filter(Node.role_list.any(name='controller')).\
            order_by(Node.id)


class TestNovaOrchestratorSerializer(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestNovaOrchestratorSerializer, self).setUp()
        self.cluster = self.create_env('multinode')

    def create_env(self, mode, network_manager='FlatDHCPManager'):
        node_args = [
            {'roles': ['controller', 'cinder'], 'pending_addition': True},
            {'roles': ['compute', 'cinder'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True},
            {'roles': [], 'pending_roles': ['cinder'],
             'pending_addition': True}]
        cluster = self.env.create(
            cluster_kwargs={
                'mode': mode,
                'net_manager': network_manager},
            nodes_kwargs=node_args)

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        TaskHelper.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    @property
    def serializer(self):
        return DeploymentMultinodeSerializer

    def assert_roles_flattened(self, nodes):
        self.assertEquals(len(nodes), 6)
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
            self.assertEquals(serialized_node, expected_node)

    def test_serialize_node(self):
        node = self.env.create_node(
            api=True, cluster_id=self.cluster.id, pending_addition=True)
        TaskHelper.prepare_for_deployment(self.cluster.nodes)

        node_db = self.db.query(Node).get(node['id'])
        serialized_data = self.serializer.serialize_node(node_db, 'controller')

        self.assertEquals(serialized_data['role'], 'controller')
        self.assertEquals(serialized_data['uid'], str(node_db.id))
        self.assertEquals(serialized_data['status'], node_db.status)
        self.assertEquals(serialized_data['online'], node_db.online)
        self.assertEquals(serialized_data['fqdn'],
                          'node-%d.%s' % (node_db.id, settings.DNS_DOMAIN))
        self.assertEquals(
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
            self.assertEquals(node['public_netmask'], '255.255.255.0')
            self.assertEquals(node['internal_netmask'], '255.255.255.0')
            self.assertEquals(node['storage_netmask'], '255.255.255.0')
            self.assertEquals(node['uid'], str(node_db.id))
            self.assertEquals(node['name'], 'node-%d' % node_db.id)
            self.assertEquals(node['fqdn'], 'node-%d.%s' %
                              (node_db.id, settings.DNS_DOMAIN))

        # Check uncommon attrs
        node_uids = sorted(set([n['uid'] for n in node_list]))
        expected_list = [
            {
                'roles': ['controller', 'cinder'],
                'attrs': {
                    'uid': node_uids[0],
                    'internal_address': '192.168.0.2',
                    'public_address': '172.16.0.2',
                    'storage_address': '192.168.1.2'}},
            {
                'roles': ['compute', 'cinder'],
                'attrs': {
                    'uid': node_uids[1],
                    'internal_address': '192.168.0.3',
                    'public_address': '172.16.0.3',
                    'storage_address': '192.168.1.3'}},
            {
                'roles': ['compute'],
                'attrs': {
                    'uid': node_uids[2],
                    'internal_address': '192.168.0.4',
                    'public_address': '172.16.0.4',
                    'storage_address': '192.168.1.4'}},
            {
                'roles': ['cinder'],
                'attrs': {
                    'uid': node_uids[3],
                    'internal_address': '192.168.0.5',
                    'public_address': '172.16.0.5',
                    'storage_address': '192.168.1.5'}}]

        for expected in expected_list:
            attrs = expected['attrs']

            for role in expected['roles']:
                nodes = self.filter_by_role(node_list, role)
                node = self.filter_by_uid(nodes, attrs['uid'])[0]

                self.assertEquals(attrs['internal_address'],
                                  node['internal_address'])
                self.assertEquals(attrs['public_address'],
                                  node['public_address'])
                self.assertEquals(attrs['storage_address'],
                                  node['storage_address'])

    def test_vlan_manager(self):
        cluster = self.create_env('multinode')
        data = {'net_manager': 'VlanManager'}
        url = reverse('NovaNetworkConfigurationHandler',
                      kwargs={'cluster_id': cluster.id})
        self.app.put(url, json.dumps(data),
                     headers=self.default_headers,
                     expect_errors=False)
        facts = self.serializer.serialize(cluster, cluster.nodes)

        for fact in facts:
            self.assertEquals(fact['vlan_interface'], 'eth0')
            self.assertEquals(fact['fixed_interface'], 'eth0')
            self.assertEquals(
                fact['novanetwork_parameters']['network_manager'],
                'VlanManager')
            self.assertEquals(
                fact['novanetwork_parameters']['num_networks'], 1)
            self.assertEquals(
                fact['novanetwork_parameters']['vlan_start'], 103)
            self.assertEquals(
                fact['novanetwork_parameters']['network_size'], 256)

    def test_floatin_ranges_generation(self):
        # Set ip ranges for floating ips
        ranges = [['172.16.0.2', '172.16.0.4'],
                  ['172.16.0.3', '172.16.0.5'],
                  ['172.16.0.10', '172.16.0.12']]

        floating_network_group = self.db.query(NetworkGroup).filter(
            NetworkGroup.name == 'floating'
        ).filter(
            NetworkGroup.cluster_id == self.cluster.id).first()

        # Remove floating ip addr ranges
        self.db.query(IPAddrRange).filter(
            IPAddrRange.network_group_id == floating_network_group.id).delete()

        # Add new ranges
        for ip_range in ranges:
            new_ip_range = IPAddrRange(
                first=ip_range[0],
                last=ip_range[1],
                network_group_id=floating_network_group.id)

            self.db.add(new_ip_range)
        self.db.commit()
        facts = self.serializer.serialize(self.cluster, self.cluster.nodes)

        for fact in facts:
            self.assertEquals(
                fact['floating_network_range'],
                ['172.16.0.2-172.16.0.4',
                 '172.16.0.3-172.16.0.5',
                 '172.16.0.10-172.16.0.12'])

    def test_configure_interfaces_untagged_network(self):
        for network in self.db.query(NetworkGroup).all():
            network.vlan_start = None
        self.db.commit()
        node_db = sorted(self.cluster.nodes, key=lambda n: n.id)[0]
        from nailgun.orchestrator.deployment_serializers \
            import NovaNetworkDeploymentSerializer
        interfaces = NovaNetworkDeploymentSerializer.\
            configure_interfaces(node_db)

        expected_interfaces = {
            'lo': {
                'interface': 'lo',
                'ipaddr': ['127.0.0.1/8']},
            'eth0': {
                'interface': 'eth0',
                'ipaddr': [
                    '192.168.0.2/24',
                    '172.16.0.2/24',
                    '192.168.1.2/24'],
                'gateway': '172.16.0.1'},
            'eth1': {
                'interface': 'eth1',
                'ipaddr': [
                    '10.20.0.129/24']}}

        self.datadiff(expected_interfaces, interfaces)


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
                {'roles': ['cinder'], 'pending_addition': True}])

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        TaskHelper.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    @property
    def serializer(self):
        return DeploymentHASerializer

    def test_set_deployment_priorities(self):
        nodes = [
            {'role': 'primary-swift-proxy'},
            {'role': 'swift-proxy'},
            {'role': 'storage'},
            {'role': 'primary-controller'},
            {'role': 'controller'},
            {'role': 'controller'},
            {'role': 'ceph-osd'},
            {'role': 'other'}
        ]
        self.serializer.set_deployment_priorities(nodes)
        expected_priorities = [
            {'role': 'primary-swift-proxy', 'priority': 100},
            {'role': 'swift-proxy', 'priority': 200},
            {'role': 'storage', 'priority': 300},
            {'role': 'primary-controller', 'priority': 400},
            {'role': 'controller', 'priority': 500},
            {'role': 'controller', 'priority': 600},
            {'role': 'ceph-osd', 'priority': 700},
            {'role': 'other', 'priority': 700}
        ]
        self.assertEquals(expected_priorities, nodes)

    def test_node_list(self):
        serialized_nodes = self.serializer.node_list(self.cluster.nodes)

        for node in serialized_nodes:
            # Each node has swift_zone
            self.assertEquals(node['swift_zone'], node['uid'])

    def test_get_common_attrs(self):
        attrs = self.serializer.get_common_attrs(self.cluster)
        # vips
        self.assertEquals(attrs['management_vip'], '192.168.0.8')
        self.assertEquals(attrs['public_vip'], '172.16.0.8')

        # last_contrller
        controllers = self.get_controllers(self.cluster.id)
        self.assertEquals(attrs['last_controller'],
                          'node-%d' % controllers[-1].id)

        # primary_controller
        controllers = self.filter_by_role(attrs['nodes'], 'primary-controller')
        self.assertEquals(controllers[0]['role'], 'primary-controller')

        # mountpoints and mp attrs
        self.assertEquals(
            attrs['mp'],
            [{'point': '1', 'weight': '1'},
             {'point': '2', 'weight': '2'}])


class TestNeutronOrchestratorSerializer(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestNeutronOrchestratorSerializer, self).setUp()
        self.cluster = self.create_env('multinode')

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
        TaskHelper.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    @property
    def serializer(self):
        return DeploymentMultinodeSerializer

    def assert_roles_flattened(self, nodes):
        self.assertEquals(len(nodes), 6)
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
            self.assertEquals(serialized_node, expected_node)

    def test_serialize_node(self):
        node = self.env.create_node(
            api=True, cluster_id=self.cluster.id, pending_addition=True)
        TaskHelper.prepare_for_deployment(self.cluster.nodes)

        node_db = self.db.query(Node).get(node['id'])
        serialized_data = self.serializer.serialize_node(node_db, 'controller')

        self.assertEquals(serialized_data['role'], 'controller')
        self.assertEquals(serialized_data['uid'], str(node_db.id))
        self.assertEquals(serialized_data['status'], node_db.status)
        self.assertEquals(serialized_data['online'], node_db.online)
        self.assertEquals(serialized_data['fqdn'],
                          'node-%d.%s' % (node_db.id, settings.DNS_DOMAIN))

    def test_node_list(self):
        node_list = self.serializer.get_common_attrs(self.cluster)['nodes']

        # Check right nodes count with right roles
        self.assert_roles_flattened(node_list)

        # Check common attrs
        for node in node_list:
            node_db = self.db.query(Node).get(int(node['uid']))
            self.assertEquals(node['public_netmask'], '255.255.255.0')
            self.assertEquals(node['internal_netmask'], '255.255.255.0')
            self.assertEquals(node['storage_netmask'], '255.255.255.0')
            self.assertEquals(node['uid'], str(node_db.id))
            self.assertEquals(node['name'], 'node-%d' % node_db.id)
            self.assertEquals(node['fqdn'], 'node-%d.%s' %
                                            (node_db.id, settings.DNS_DOMAIN))

        # Check uncommon attrs
        node_uids = sorted(set([n['uid'] for n in node_list]))
        expected_list = [
            {
                'roles': ['controller', 'cinder'],
                'attrs': {
                    'uid': node_uids[0],
                    'internal_address': '192.168.0.2',
                    'public_address': '172.16.0.2',
                    'storage_address': '192.168.1.2'}},
            {
                'roles': ['compute', 'cinder'],
                'attrs': {
                    'uid': node_uids[1],
                    'internal_address': '192.168.0.3',
                    'public_address': '172.16.0.3',
                    'storage_address': '192.168.1.3'}},
            {
                'roles': ['compute'],
                'attrs': {
                    'uid': node_uids[2],
                    'internal_address': '192.168.0.4',
                    'public_address': '172.16.0.4',
                    'storage_address': '192.168.1.4'}},
            {
                'roles': ['cinder'],
                'attrs': {
                    'uid': node_uids[3],
                    'internal_address': '192.168.0.5',
                    'public_address': '172.16.0.5',
                    'storage_address': '192.168.1.5'}}]

        for expected in expected_list:
            attrs = expected['attrs']

            for role in expected['roles']:
                nodes = self.filter_by_role(node_list, role)
                node = self.filter_by_uid(nodes, attrs['uid'])[0]

                self.assertEquals(attrs['internal_address'],
                                  node['internal_address'])
                self.assertEquals(attrs['public_address'],
                                  node['public_address'])
                self.assertEquals(attrs['storage_address'],
                                  node['storage_address'])

    def test_neutron_l3_gateway(self):
        cluster = self.create_env('multinode', 'gre')
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
        self.assertEquals(
            pd_nets["net04_ext"]["L3"]["gateway"],
            test_gateway
        )

    def test_gre_segmentation(self):
        cluster = self.create_env('multinode', 'gre')
        facts = self.serializer.serialize(cluster, cluster.nodes)

        for fact in facts:
            self.assertEquals(
                fact['quantum_settings']['L2']['segmentation_type'], 'gre')
            self.assertEquals(
                'br-prv' in fact['network_scheme']['endpoints'], False)
            self.assertEquals(
                'private' in (fact['network_scheme']['roles']), False)

    def _create_cluster_for_vlan_splinters(self, segment_type='gre'):
        meta = {
            'interfaces': [
                {'name': 'eth0', 'mac': self.env._generate_random_mac()},
                {'name': 'eth1', 'mac': self.env._generate_random_mac()},
                {'name': 'eth2', 'mac': self.env._generate_random_mac()},
                {'name': 'eth3', 'mac': self.env._generate_random_mac()},
                {'name': 'eth4', 'mac': self.env._generate_random_mac()}
            ]
        }
        cluster = self.env.create(
            cluster_kwargs={
                'mode': 'multinode',
                'net_provider': 'neutron',
                'net_segment_type': segment_type
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True,
                 'meta': meta}
            ]
        )

        cluster_db = self.db.query(Cluster).get(cluster['id'])
        TaskHelper.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    def test_vlan_splinters_disabled(self):
        cluster = self._create_cluster_for_vlan_splinters()
        cluster_id = cluster.id
        editable_attrs = cluster.attributes.editable.copy()

        # Remove 'vlan_splinters' attribute and check results.

        editable_attrs['common'].pop('vlan_splinters', None)
        db.refresh(cluster.attributes)
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        cluster = self.db.query(Cluster).get(cluster_id)
        editable_attrs = cluster.attributes.editable.copy()
        self.assertNotIn('vlan_splinters', editable_attrs['common'])

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertNotIn('vlan_splinters', L2_attrs)
            self.assertNotIn('trunks', L2_attrs)

        # Set 'vlan_splinters' to 'some_text' and check results.

        editable_attrs['common']['vlan_splinters'] = {'value': 'some_text'}
        db.refresh(cluster.attributes)
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        cluster = self.db.query(Cluster).get(cluster_id)
        editable_attrs = cluster.attributes.editable
        self.assertEquals(editable_attrs['common']['vlan_splinters']['value'],
                          'some_text')

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertNotIn('vlan_splinters', L2_attrs)
            self.assertNotIn('trunks', L2_attrs)

        # Set 'vlan_splinters' to 'disabled' and check results.

        editable_attrs['common']['vlan_splinters'] = {'value': 'disabled'}
        db.refresh(cluster.attributes)
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        cluster = self.db.query(Cluster).get(cluster_id)
        editable_attrs = cluster.attributes.editable
        self.assertEquals(editable_attrs['common']['vlan_splinters']['value'],
                          'disabled')

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertIn('vlan_splinters', L2_attrs)
            self.assertEquals(L2_attrs['vlan_splinters'], 'off')
            self.assertNotIn('trunks', L2_attrs)

    def test_hard_vlan_splinters_in_gre(self):
        cluster = self._create_cluster_for_vlan_splinters('gre')
        editable_attrs = cluster.attributes.editable.copy()

        # Set 'vlan_splinters' to 'hard' and check results.
        editable_attrs['common'].setdefault(
            'vlan_splinters', {'value': 'hard'}
        )['value'] = 'hard'
        db.refresh(cluster.attributes)
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
            self.assertEquals(L2_attrs['vlan_splinters'], 'auto')
            self.assertIn('trunks', L2_attrs)
            self.assertIn(0, L2_attrs['trunks'])
            map(
                lambda n: vlan_set.remove(n) if n else None,
                L2_attrs['trunks']
            )
        self.assertEquals(len(vlan_set), 0)

    def test_hard_vlan_splinters_in_vlan(self):
        cluster = self._create_cluster_for_vlan_splinters('vlan')
        editable_attrs = cluster.attributes.editable.copy()

        # Set 'vlan_splinters' to 'hard' and check results.
        editable_attrs['common'].setdefault(
            'vlan_splinters', {'value': 'hard'}
        )['value'] = 'hard'
        db.refresh(cluster.attributes)
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        vlan_set = set(
            [ng.vlan_start for ng in cluster.network_groups if ng.vlan_start]
        )
        private_vlan_range = cluster.neutron_config.L2["phys_nets"][
            "physnet2"]["vlan_range"]
        vlan_set.update(xrange(*private_vlan_range))
        vlan_set.add(private_vlan_range[1])

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertIn('vlan_splinters', L2_attrs)
            self.assertEquals(L2_attrs['vlan_splinters'], 'auto')
            self.assertIn('trunks', L2_attrs)
            self.assertIn(0, L2_attrs['trunks'])
            map(
                lambda n: vlan_set.remove(n) if n else None,
                L2_attrs['trunks']
            )
        self.assertEquals(len(vlan_set), 0)

    def test_soft_vlan_splinters_in_vlan(self):
        cluster = self._create_cluster_for_vlan_splinters('vlan')
        editable_attrs = cluster.attributes.editable.copy()

        # Set 'vlan_splinters' to 'soft' and check results.
        editable_attrs['common'].setdefault(
            'vlan_splinters', {'value': 'soft'}
        )['value'] = 'soft'
        db.refresh(cluster.attributes)
        cluster.attributes.editable = editable_attrs
        self.db.commit()

        node = self.serializer.serialize(cluster, cluster.nodes)[0]
        interfaces = node['network_scheme']['interfaces']
        for iface_attrs in interfaces.itervalues():
            self.assertIn('L2', iface_attrs)
            L2_attrs = iface_attrs['L2']
            self.assertIn('vlan_splinters', L2_attrs)
            self.assertEquals(L2_attrs['vlan_splinters'], 'auto')
            self.assertIn('trunks', L2_attrs)
            self.assertEquals(L2_attrs['trunks'], [0])


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
        TaskHelper.prepare_for_deployment(cluster_db.nodes)
        return cluster_db

    @property
    def serializer(self):
        return DeploymentHASerializer

    def test_node_list(self):
        serialized_nodes = self.serializer.node_list(self.cluster.nodes)

        for node in serialized_nodes:
            # Each node has swift_zone
            self.assertEquals(node['swift_zone'], node['uid'])

    def test_get_common_attrs(self):
        attrs = self.serializer.get_common_attrs(self.cluster)
        # vips
        self.assertEquals(attrs['management_vip'], '192.168.0.8')
        self.assertEquals(attrs['public_vip'], '172.16.0.8')

        # last_contrller
        controllers = self.get_controllers(self.cluster.id)
        self.assertEquals(attrs['last_controller'],
                          'node-%d' % controllers[-1].id)

        # primary_controller
        controllers = self.filter_by_role(attrs['nodes'], 'primary-controller')
        self.assertEquals(controllers[0]['role'], 'primary-controller')

        # mountpoints and mp attrs
        self.assertEquals(
            attrs['mp'],
            [{'point': '1', 'weight': '1'},
             {'point': '2', 'weight': '2'}])
