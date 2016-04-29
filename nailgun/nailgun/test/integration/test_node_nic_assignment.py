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

from copy import deepcopy
import mock
from netaddr import IPNetwork

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.db.sqlalchemy.models import NetworkNICAssignment
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestClusterHandlers(BaseIntegrationTest):

    def test_assigned_networks_when_node_added(self):
        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()}])

        node = self.env.create_node(api=True, meta=meta, mac=mac)
        self.env.create_cluster(
            api=True,
            editable_attributes={'public_network_assignment': {
                'assign_to_all_nodes': {'value': True}}},
            nodes=[node['id']])

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)

        for resp_nic in resp.json_body:
            net_names = [net['name'] for net in resp_nic['assigned_networks']]
            if resp_nic['mac'] == mac:
                self.assertTrue("fuelweb_admin" in net_names)
            else:
                self.assertTrue("public" in net_names)
            self.assertGreater(len(resp_nic['assigned_networks']), 0)

    def test_assignment_is_removed_when_delete_node_from_cluster(self):
        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac)
        cluster = self.env.create_cluster(api=True, nodes=[node['id']])
        resp = self.app.put(
            reverse('ClusterHandler', kwargs={'obj_id': cluster['id']}),
            jsonutils.dumps({'nodes': []}),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        for resp_nic in resp.json_body:
            self.assertEqual(resp_nic['assigned_networks'], [])

    def test_assignment_is_removed_when_delete_cluster(self):
        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac)
        cluster = self.env.create_cluster(api=True, nodes=[node['id']])
        self.db.delete(cluster)
        self.db.commit()

        net_assignment = self.db.query(NetworkNICAssignment).all()
        self.assertEqual(len(net_assignment), 0)


class TestNodeHandlers(BaseIntegrationTest):

    def test_network_assignment_when_node_created_and_added(self):
        cluster = self.env.create_cluster(
            api=True,
            editable_attributes={'public_network_assignment': {
                'assign_to_all_nodes': {'value': True}}})
        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac,
                                    cluster_id=cluster['id'])
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        for resp_nic in resp.json_body:
            net_names = [net['name'] for net in resp_nic['assigned_networks']]
            if resp_nic['mac'] == mac:
                self.assertTrue("fuelweb_admin" in net_names)
            else:
                self.assertTrue("public" in net_names)
            self.assertGreater(len(resp_nic['assigned_networks']), 0)

    def test_network_assignment_when_node_added(self):
        cluster = self.env.create_cluster(
            api=True,
            editable_attributes={'public_network_assignment': {
                'assign_to_all_nodes': {'value': True}}})
        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac)
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node['id'], 'cluster_id': cluster['id']}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        for resp_nic in response:
            net_names = [net['name'] for net in resp_nic['assigned_networks']]
            if resp_nic['mac'] == mac:
                self.assertTrue("fuelweb_admin" in net_names)
            else:
                self.assertTrue("public" in net_names)
            self.assertGreater(len(resp_nic['assigned_networks']), 0)

    def _add_node_with_pxe_on_eth2(self, cluster_id, **kwargs):
        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': self.env.generate_random_mac()},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()},
             {'name': 'eth2', 'mac': mac}])
        return self.env.create_node(
            api=True, meta=meta, mac=mac, cluster_id=cluster_id, **kwargs)

    @mock.patch('nailgun.rpc.cast')
    def test_default_network_assignment_for_multiple_node_groups(self, _):
        cluster = self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu},
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.tun})

        node1 = self._add_node_with_pxe_on_eth2(cluster['id'])

        node_group = self.env.create_node_group(api=False)
        resp = self.env.setup_networks_for_nodegroup(
            cluster_id=cluster['id'], node_group=node_group,
            cidr_start='199.99')
        self.assertEqual(resp.status_code, 200)
        node2 = self._add_node_with_pxe_on_eth2(cluster['id'], ip='199.99.9.3')
        self.assertEqual(node2['group_id'], node_group.id)

        for node in [node1, node2]:
            resp = self.app.get(
                reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
                headers=self.default_headers)
            self.assertEqual(resp.status_code, 200)
            nics = resp.json_body
            node_net_names = []
            pxe_found = False
            for nic in nics:
                net_names = [net['name'] for net in nic['assigned_networks']]
                node_net_names.extend(net_names)
                if nic['pxe']:
                    self.assertIn("fuelweb_admin", net_names)
                    self.assertEqual(nic['name'], 'eth2')
                    pxe_found = True
            self.assertTrue(pxe_found)
            self.assertEqual(len(node_net_names), len(set(node_net_names)))

    def test_novanet_assignment_when_network_cfg_changed_then_node_added(self):
        cluster = self.env.create_cluster(
            api=True,
            net_provider=consts.CLUSTER_NET_PROVIDERS.nova_network)

        resp = self.env.nova_networks_get(cluster['id'])
        nets = resp.json_body
        for net in nets['networks']:
            if net['name'] == 'management':
                net['vlan_start'] = None

        resp = self.env.nova_networks_put(cluster['id'], nets)
        self.assertEqual(resp.status_code, 200)

        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()},
             {'name': 'eth2', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac)
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node['id'], 'cluster_id': cluster['id']}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        net_name_per_nic = [['fuelweb_admin', 'storage', 'fixed'],
                            ['public'],
                            ['management']]
        for i, nic in enumerate(sorted(response, key=lambda x: x['name'])):
            net_names = set([net['name'] for net in nic['assigned_networks']])
            self.assertEqual(set(net_name_per_nic[i]), net_names)

        for net in nets['networks']:
            if net['name'] == 'public':
                net['vlan_start'] = 111
            if net['name'] == 'management':
                net['vlan_start'] = 112
        resp = self.env.nova_networks_put(cluster['id'], nets)
        self.assertEqual(resp.status_code, 200)

        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()},
             {'name': 'eth2', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac)
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node['id'], 'cluster_id': cluster['id']}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        net_name_per_nic = [['fuelweb_admin', 'storage', 'fixed',
                             'public', 'management'],
                            [], []]
        for i, nic in enumerate(sorted(response, key=lambda x: x['name'])):
            net_names = set([net['name'] for net in nic['assigned_networks']])
            self.assertEqual(set(net_name_per_nic[i]), net_names)

    def test_neutron_assignment_when_network_cfg_changed_then_node_added(self):
        cluster = self.env.create_cluster(
            api=True,
            net_provider='neutron',
            net_segment_type='vlan',
            editable_attributes={'public_network_assignment': {
                'assign_to_all_nodes': {'value': True}}})
        resp = self.env.neutron_networks_get(cluster['id'])
        nets = resp.json_body
        for net in nets['networks']:
            if net['name'] == 'management':
                net['vlan_start'] = None
        resp = self.env.neutron_networks_put(cluster['id'], nets)
        self.assertEqual(resp.status_code, 200)

        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()},
             {'name': 'eth2', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac)
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node['id'], 'cluster_id': cluster['id']}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        net_name_per_nic = [['fuelweb_admin', 'storage', 'private'],
                            ['public'],
                            ['management']]
        for i, nic in enumerate(sorted(response, key=lambda x: x['name'])):
            net_names = set([net['name'] for net in nic['assigned_networks']])
            self.assertEqual(set(net_name_per_nic[i]), net_names)

        for net in nets['networks']:
            if net['name'] == 'public':
                net['vlan_start'] = 111
            if net['name'] == 'management':
                net['vlan_start'] = 112
        resp = self.env.neutron_networks_put(cluster['id'], nets)
        self.assertEqual(resp.status_code, 200)

        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()},
             {'name': 'eth2', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac)
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node['id'], 'cluster_id': cluster['id']}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        net_name_per_nic = [['fuelweb_admin', 'storage', 'public',
                             'management', 'private'],
                            [], []]
        for i, nic in enumerate(sorted(response, key=lambda x: x['name'])):
            net_names = set([net['name'] for net in nic['assigned_networks']])
            self.assertEqual(set(net_name_per_nic[i]), net_names)

    def test_assignment_is_removed_when_delete_node_from_cluster(self):
        cluster = self.env.create_cluster(api=True)
        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac,
                                    cluster_id=cluster['id'])
        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node['id'], 'cluster_id': None}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        for resp_nic in response:
            self.assertEqual(resp_nic['assigned_networks'], [])

    def test_getting_default_nic_information_for_node(self):
        cluster = self.env.create_cluster(api=True)
        macs = (self.env.generate_random_mac(),
                self.env.generate_random_mac())
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': macs[0]},
             {'name': 'eth1', 'mac': macs[1]}])
        node = self.env.create_node(api=True, meta=meta, mac=macs[0],
                                    cluster_id=cluster['id'])
        resp = self.app.get(
            reverse('NodeNICsDefaultHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers
        )
        resp_macs = map(
            lambda interface: interface["mac"],
            resp.json_body
        )
        self.assertEqual(resp.status_code, 200)
        self.assertItemsEqual(macs, resp_macs)

    def test_try_add_node_with_same_mac(self):
        mac_pool = (
            self.env.generate_random_mac(),
            self.env.generate_random_mac(),
            self.env.generate_random_mac(),
            self.env.generate_random_mac(),
        )

        cluster = self.env.create_cluster(api=True)
        macs = mac_pool[0], mac_pool[1]
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': macs[0]},
             {'name': 'eth1', 'mac': macs[1]}])
        self.env.create_node(api=True, meta=meta, mac=macs[0],
                             cluster_id=cluster['id'])

        self.env.create_node(api=True, meta=meta, mac=macs[0],
                             cluster_id=cluster['id'],
                             expect_http=409)

        macs = (mac_pool[0], mac_pool[2])
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': macs[0]},
             {'name': 'eth1', 'mac': macs[1]}])
        self.env.create_node(api=True, meta=meta, mac=macs[0],
                             cluster_id=cluster['id'],
                             expect_http=409)

        macs = (mac_pool[2], mac_pool[0])
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': macs[0]},
             {'name': 'eth1', 'mac': macs[1]}])
        self.env.create_node(api=True, meta=meta, mac=macs[0],
                             cluster_id=cluster['id'],
                             expect_http=409)

        macs = (mac_pool[1], mac_pool[2])
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': macs[0]},
             {'name': 'eth1', 'mac': macs[1]}])
        self.env.create_node(api=True, meta=meta, mac=macs[0],
                             cluster_id=cluster['id'],
                             expect_http=409)

        macs = (mac_pool[2], mac_pool[1])
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': macs[0]},
             {'name': 'eth1', 'mac': macs[1]}])
        self.env.create_node(api=True, meta=meta, mac=macs[0],
                             cluster_id=cluster['id'],
                             expect_http=409)


class TestNodeNICsSerialization(BaseIntegrationTest):

    versions = [('2014.1', False),
                ('2014.1.1-5.0.1', False),
                ('2014.1.1-5.1', False),
                ('2014.1.1-5.1.1', False),
                ('2014.2-6.0', False),
                ('2014.2-6.0.1', False),
                ('2014.2-6.1', True)]

    def check_nics_interface_properties(self, handler):
        for ver, present in self.versions:
            cluster = self.env.create(
                release_kwargs={'version': ver},
                nodes_kwargs=[
                    {'roles': ['controller'],
                     'pending_addition': True,
                     'api': True}
                ]
            )
            node = self.env.nodes[0]
            resp = self.app.get(
                reverse(handler,
                        kwargs={'node_id': node.id}),
                headers=self.default_headers
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual('interface_properties' in resp.json_body[0],
                             present)
            objects.Node.delete(node)
            objects.Cluster.delete(cluster)
            self.env.nodes = []
            self.env.clusters = []

    def test_interface_properties_in_default_nic_information(self):
        self.check_nics_interface_properties('NodeNICsDefaultHandler')

    def test_interface_properties_in_current_nic_information(self):
        self.check_nics_interface_properties('NodeNICsHandler')


class TestNodeNICAdminAssigning(BaseIntegrationTest):

    def check_admin_interface(self, node_db, admin_ng, mac, ip, name):
        admin_iface = self.env.network_manager.get_admin_interface(node_db)
        self.assertEqual(admin_iface.mac, mac)
        self.assertEqual(admin_iface.ip_addr, ip)
        self.assertEqual(admin_iface.name, name)
        if not node_db.cluster:
            return
        for nic in node_db.nic_interfaces:
            if nic == admin_iface:
                self.assertIn(admin_ng, nic.assigned_networks_list)
            else:
                self.assertNotIn(admin_ng, nic.assigned_networks_list)

    def test_admin_nic_and_ip_assignment(self):
        cluster = self.env.create_cluster(api=True)
        admin_ng = objects.NetworkGroup.get_admin_network_group()
        admin_ip = str(IPNetwork(admin_ng.cidr)[0])
        mac1, mac2 = (self.env.generate_random_mac(),
                      self.env.generate_random_mac())
        meta = self.env.default_metadata()
        meta['interfaces'] = [{'name': 'eth1', 'mac': mac2, 'ip': admin_ip,
                               'pxe': True},
                              {'name': 'eth0', 'mac': mac1}]
        self.env.create_node(api=True, meta=meta, mac=mac2,
                             cluster_id=cluster['id'])
        node_db = self.env.nodes[0]
        self.check_admin_interface(node_db, admin_ng, mac2, admin_ip, 'eth1')

        meta = deepcopy(node_db.meta)
        for interface in meta['interfaces']:
            if interface['mac'] == mac2:
                # reset admin ip,pxe for previous admin interface
                interface['ip'] = None
                interface['pxe'] = False
            elif interface['mac'] == mac1:
                # set new admin interface
                interface['ip'] = admin_ip
                interface['pxe'] = True

        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({'id': node_db.id,
                             'mac': mac1,
                             'meta': meta}),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        self.db.refresh(node_db)
        self.check_admin_interface(node_db, admin_ng, mac1, admin_ip, 'eth0')

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node_db.id,
                              'cluster_id': None}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        self.db.refresh(node_db)
        self.check_admin_interface(node_db, admin_ng, mac1, admin_ip, 'eth0')


class TestNodePublicNetworkToNICAssignment(BaseIntegrationTest):

    def create_node_and_check_assignment(self, cluster):
        meta = self.env.default_metadata()
        admin_ip = str(IPNetwork(
            objects.NetworkGroup.get_admin_network_group().cidr)[1])
        admin_mac = self.env.generate_random_mac()
        meta['interfaces'] = [
            {'name': 'eth3', 'mac': self.env.generate_random_mac()},
            {'name': 'eth2', 'mac': self.env.generate_random_mac()},
            {'name': 'eth0', 'mac': admin_mac,
             'ip': admin_ip, 'pxe': True},
            {'name': 'eth1', 'mac': self.env.generate_random_mac()}
        ]
        node = self.env.create_node(
            api=True, meta=meta, mac=admin_mac, ip=admin_ip,
            cluster_id=cluster.id)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        eth1 = [nic for nic in resp.json_body if nic['name'] == 'eth1']
        self.assertEqual(len(eth1), 1)
        self.assertEqual(
            len(filter(lambda n: n['name'] == 'public',
                       eth1[0]['assigned_networks'])),
            1)

    def test_nova_net_public_network_assigned_to_second_nic_by_name(self):
        cluster = self.env.create_cluster(
            api=True,
            net_provider=consts.CLUSTER_NET_PROVIDERS.nova_network,
            editable_attributes={'public_network_assignment': {
                'assign_to_all_nodes': {'value': True}}})
        self.create_node_and_check_assignment(cluster)

    def test_neutron_gre_public_network_assigned_to_second_nic_by_name(self):
        cluster = self.env.create_cluster(
            api=True,
            net_provider='neutron',
            net_segment_type='gre',
            editable_attributes={'public_network_assignment': {
                'assign_to_all_nodes': {'value': True}}})
        self.create_node_and_check_assignment(cluster)

    def test_neutron_tun_public_network_assigned_to_second_nic_by_name(self):
        cluster = self.env.create_cluster(
            api=True,
            net_provider='neutron',
            net_segment_type='tun',
            editable_attributes={'public_network_assignment': {
                'assign_to_all_nodes': {'value': True}}})
        self.create_node_and_check_assignment(cluster)

    def test_neutron_vlan_public_network_assigned_to_second_nic_by_name(self):
        cluster = self.env.create_cluster(
            api=True,
            net_provider='neutron',
            net_segment_type='vlan',
            editable_attributes={'public_network_assignment': {
                'assign_to_all_nodes': {'value': True}}})
        self.create_node_and_check_assignment(cluster)


class TestNodeNICsHandlersValidation(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeNICsHandlersValidation, self).setUp()
        meta = self.env.default_metadata()
        meta["interfaces"] = [
            {'name': 'eth0', 'mac': self.env.generate_random_mac(),
             'pxe': True},
            {'name': 'eth1', 'mac': self.env.generate_random_mac()},
        ]
        self.env.create(
            cluster_kwargs={
                "net_provider": "neutron",
                "net_segment_type": "gre"
            },
            nodes_kwargs=[
                {"api": True, "pending_addition": True, 'meta': meta}
            ]
        )
        resp = self.app.get(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0]["id"]}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.data = resp.json_body
        self.nics_w_nets = filter(lambda nic: nic.get("assigned_networks"),
                                  self.data)
        self.assertGreater(len(self.nics_w_nets), 0)

    def put_single(self):
        return self.env.node_nics_put(self.env.nodes[0]["id"], self.data,
                                      expect_errors=True)

    def put_collection(self):
        nodes_list = [{"id": self.env.nodes[0]["id"],
                       "interfaces": self.data}]
        return self.env.node_collection_nics_put(nodes_list,
                                                 expect_errors=True)

    def node_nics_put_check_error(self, message):
        for put_func in (self.put_single, self.put_collection):
            resp = put_func()
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(resp.json_body["message"], message)

    def test_assignment_change_failed_assigned_network_wo_id(self):
        self.nics_w_nets[0]["assigned_networks"] = [{}]

        self.node_nics_put_check_error(
            "Node '{0}', interface '{1}': each assigned network should "
            "have ID".format(self.env.nodes[0]["id"],
                             self.nics_w_nets[0]['id'])
        )

    def test_assignment_change_failed_network_not_in_node_group(self):
        net_id = -1
        self.nics_w_nets[0]["assigned_networks"].append({"id": net_id})
        self.node_nics_put_check_error(
            "Node '{0}': networks with IDs '{1}' cannot be used "
            "because they are not in node group '{2}'"
            .format(self.env.nodes[0]["id"], net_id, 'default')
        )

    def test_assignment_change_failed_network_left_unassigned(self):
        net_id = self.nics_w_nets[0]['assigned_networks'][1]['id']
        del self.nics_w_nets[0]['assigned_networks'][1]
        self.node_nics_put_check_error(
            "Node '{0}': {1} network(s) are left unassigned"
            .format(self.env.nodes[0]['id'], net_id)
        )

    def test_nic_change_failed_node_has_unknown_interface(self):
        nic_id = -1
        self.nics_w_nets[0]["id"] = nic_id

        self.node_nics_put_check_error(
            "Node '{0}': there is no interface with ID '{1}'"
            " in DB".format(self.env.nodes[0]["id"], nic_id)
        )

    def test_nic_assignment_failed_assign_admin_net_to_non_pxe_iface(self):
        admin_net = self.nics_w_nets[0]["assigned_networks"][0]
        del self.nics_w_nets[0]["assigned_networks"][0]
        self.nics_w_nets[1]["assigned_networks"].append(admin_net)
        self.node_nics_put_check_error(
            "Node '{0}': admin network can not be assigned to non-pxe"
            " interface eth1".format(self.env.nodes[0]["id"])
        )

    def test_try_net_assignment_for_node_not_in_cluster(self):
        node = self.env.create_node()

        resp = self.env.node_nics_put(
            node.id,
            self.data,
            expect_errors=True
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("node is not added to any cluster",
                      resp.json_body['message'])


class TestPublicNetworkAssigment(BaseIntegrationTest):
    def setUp(self):
        super(TestPublicNetworkAssigment, self).setUp()
        self.default_networks = [u'fuelweb_admin', u'management',
                                 u'storage', u'private']
        self.public_networks = ['public']

    def set_assign_public_to_all_nodes(self, cluster, value):
        attrs = {
            'public_network_assignment': {
                'assign_to_all_nodes': {
                    'value': value
                }
            }
        }
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster.id}),
            params=jsonutils.dumps({'editable': attrs}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        ejson = resp.json_body['editable']
        self.assertEqual(
            ejson['public_network_assignment']['assign_to_all_nodes']['value'],
            value
        )

    def check_network_assigments(self, node, networks_by, key='mac'):
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)

        for resp_nic in resp.json_body:
            net_names = [net['name'] for net in resp_nic['assigned_networks']]
            nets = networks_by.get(resp_nic[key], [])
            self.assertListEqual(nets, net_names)

    def check_node_public_ip_assigment(self, cluster, node, public_ip):
        node_db = objects.Node.get_by_uid(node['id'])
        nm = objects.Cluster.get_network_manager(cluster)
        nets = nm.get_node_networks(node_db)
        ng = nm.get_network_by_netname(consts.NETWORKS.public, nets)
        self.assertEqual(public_ip, ng.get('ip'))

    def create_node_with_preset_macs(self, cluster, roles=None, iface_count=2):
        macs = []
        meta = self.env.default_metadata()
        interfaces = []
        for i in range(iface_count):
            mac = self.env.generate_random_mac()
            macs.append(mac)
            interfaces.append({'name': 'eth%d' % i, 'mac': mac})

        self.env.set_interfaces_in_meta(
            meta,
            interfaces)

        node = self.env.create_node(api=True, meta=meta, mac=macs[0],
                                    roles=roles, cluster_id=cluster.id)
        return node, macs

    def test_only_controllers_changed_to_all_change(self):
        self.env.create_cluster(api=True)
        cluster = self.env.clusters[0]

        node1, macs1 = self.create_node_with_preset_macs(cluster,
                                                         ['controller'])
        self.check_network_assigments(node1, {
            macs1[0]: self.default_networks,
            macs1[1]: self.public_networks})

        node2, macs2 = self.create_node_with_preset_macs(cluster,
                                                         roles=['cinder'])
        self.check_network_assigments(node2, {
            macs2[0]: self.default_networks,
            macs2[1]: []})

        self.set_assign_public_to_all_nodes(cluster, True)

        self.check_network_assigments(node1, {
            macs1[0]: self.default_networks,
            macs1[1]: self.public_networks})
        self.check_network_assigments(node2, {
            macs2[0]: self.default_networks,
            macs2[1]: self.public_networks})

        objects.Cluster.prepare_for_deployment(cluster)
        self.check_node_public_ip_assigment(cluster, node1, '172.16.0.2/24')
        self.check_node_public_ip_assigment(cluster, node2, '172.16.0.3/24')

    def test_all_to_only_controllers_change(self):
        self.env.create_cluster(
            api=True,
            editable_attributes={'public_network_assignment': {
                'assign_to_all_nodes': {'value': True}}})

        cluster = self.env.clusters[0]

        node1, macs1 = self.create_node_with_preset_macs(cluster,
                                                         ['controller'])
        self.check_network_assigments(node1, {
            macs1[0]: self.default_networks,
            macs1[1]: self.public_networks})

        node2, macs2 = self.create_node_with_preset_macs(cluster,
                                                         ['cinder'])
        self.check_network_assigments(node2, {
            macs2[0]: self.default_networks,
            macs2[1]: self.public_networks})

        self.set_assign_public_to_all_nodes(cluster, False)

        self.check_network_assigments(node1, {
            macs1[0]: self.default_networks,
            macs1[1]: self.public_networks})
        self.check_network_assigments(node2, {
            macs2[0]: self.default_networks,
            macs2[1]: []})

        objects.Cluster.prepare_for_deployment(cluster)
        self.check_node_public_ip_assigment(cluster, node1, '172.16.0.2/24')
        with self.assertRaises(IndexError):
            self.check_node_public_ip_assigment(cluster, node2, None)

    def test_assign_and_deassign_to_bonds(self):
        self.env.create_cluster(
            api=True,
            editable_attributes={'public_network_assignment': {
                'assign_to_all_nodes': {'value': True}}})
        cluster = self.env.clusters[0]

        node1, macs1 = self.create_node_with_preset_macs(cluster,
                                                         ['controller'],
                                                         3)
        self.env.make_bond_via_api('ovsbond0',
                                   consts.BOND_MODES.balance_tcp,
                                   ['eth1', 'eth2'],
                                   node1['id'])

        node2, macs2 = self.create_node_with_preset_macs(cluster,
                                                         ['cinder'],
                                                         3)
        self.env.make_bond_via_api('ovsbond0',
                                   consts.BOND_MODES.balance_tcp,
                                   ['eth1', 'eth2'],
                                   node2['id'])

        self.check_network_assigments(node1, {
            'eth0': self.default_networks,
            'ovsbond0': self.public_networks},
            key='name')
        self.check_network_assigments(node2, {
            'eth0': self.default_networks,
            'ovsbond0': self.public_networks},
            key='name')

        self.set_assign_public_to_all_nodes(cluster, False)

        self.check_network_assigments(node1, {
            'eth0': self.default_networks,
            'ovsbond0': self.public_networks},
            key='name')
        self.check_network_assigments(node2, {
            'eth0': self.default_networks,
            'ovsbond0': []},
            key='name')

        self.set_assign_public_to_all_nodes(cluster, True)

        self.check_network_assigments(node1, {
            'eth0': self.default_networks,
            'ovsbond0': self.public_networks},
            key='name')
        self.check_network_assigments(node2, {
            'eth0': self.default_networks,
            'ovsbond0': self.public_networks},
            key='name')

        objects.Cluster.prepare_for_deployment(cluster)
        self.check_node_public_ip_assigment(cluster, node1, '172.16.0.2/24')
        self.check_node_public_ip_assigment(cluster, node2, '172.16.0.3/24')
