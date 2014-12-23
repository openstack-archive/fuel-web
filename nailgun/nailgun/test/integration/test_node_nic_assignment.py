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
from netaddr import IPNetwork

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkNICAssignment
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestClusterHandlers(BaseIntegrationTest):

    def test_assigned_networks_when_node_added(self):
        mac = self.env.generate_random_mac()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(
            meta,
            [{'name': 'eth0', 'mac': mac},
             {'name': 'eth1', 'mac': self.env.generate_random_mac()}])

        node = self.env.create_node(api=True, meta=meta, mac=mac)
        self.env.create_cluster(api=True, nodes=[node['id']])

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
        cluster_db = self.db.query(Cluster).get(cluster['id'])
        self.db.delete(cluster_db)
        self.db.commit()

        net_assignment = self.db.query(NetworkNICAssignment).all()
        self.assertEqual(len(net_assignment), 0)


class TestNodeHandlers(BaseIntegrationTest):

    def test_network_assignment_when_node_created_and_added(self):
        cluster = self.env.create_cluster(api=True)
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
        cluster = self.env.create_cluster(api=True)
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

    def test_novanet_assignment_when_network_cfg_changed_then_node_added(self):
        cluster = self.env.create_cluster(api=True)

        resp = self.env.nova_networks_get(cluster['id'])
        nets = resp.json_body
        for net in nets['networks']:
            if net['name'] == 'management':
                net['vlan_start'] = None

        resp = self.env.nova_networks_put(cluster['id'], nets)
        self.assertEqual(resp.status_code, 202)
        task = resp.json_body
        self.assertEqual(task['status'], 'ready')

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
        self.assertEqual(resp.status_code, 202)
        task = resp.json_body
        self.assertEqual(task['status'], 'ready')

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
        cluster = self.env.create_cluster(api=True,
                                          net_provider='neutron',
                                          net_segment_type='vlan')
        resp = self.env.neutron_networks_get(cluster['id'])
        nets = resp.json_body
        for net in nets['networks']:
            if net['name'] == 'management':
                net['vlan_start'] = None
        resp = self.env.neutron_networks_put(cluster['id'], nets)
        self.assertEqual(resp.status_code, 200)
        task = resp.json_body
        self.assertEqual(task['status'], 'ready')

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
        task = resp.json_body
        self.assertEqual(task['status'], 'ready')

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


class TestNodeNICAdminAssigning(BaseIntegrationTest):

    def test_admin_nic_and_ip_assignment(self):
        cluster = self.env.create_cluster(api=True)
        admin_ip = str(IPNetwork(
            self.env.network_manager.get_admin_network_group().cidr)[0])
        mac1, mac2 = (self.env.generate_random_mac(),
                      self.env.generate_random_mac())
        meta = self.env.default_metadata()
        meta['interfaces'] = [{'name': 'eth0', 'mac': mac1},
                              {'name': 'eth1', 'mac': mac2, 'ip': admin_ip}]
        self.env.create_node(api=True, meta=meta, mac=mac1,
                             cluster_id=cluster['id'])
        node_db = self.env.nodes[0]
        self.assertEqual(node_db.admin_interface.mac, mac2)
        self.assertEqual(node_db.admin_interface.ip_addr, admin_ip)

        meta = deepcopy(node_db.meta)
        for interface in meta['interfaces']:
            if interface['mac'] == mac2:
                # reset admin ip for previous admin interface
                interface['ip'] = None
            elif interface['mac'] == mac1:
                # set new admin interface
                interface['ip'] = admin_ip

        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({'id': node_db.id,
                             'meta': meta}),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        self.db.refresh(node_db)
        self.assertEqual(node_db.admin_interface.mac, mac2)
        self.assertEqual(node_db.admin_interface.ip_addr, None)

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{'id': node_db.id,
                              'cluster_id': None}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        self.db.refresh(node_db)
        self.assertEqual(node_db.admin_interface.mac, mac1)
        self.assertEqual(node_db.admin_interface.ip_addr, admin_ip)


class TestNodePublicNetworkToNICAssignment(BaseIntegrationTest):

    def create_node_and_check_assignment(self):
        meta = self.env.default_metadata()
        admin_ip = str(IPNetwork(
            self.env.network_manager.get_admin_network_group().cidr)[0])
        meta['interfaces'] = [
            {'name': 'eth3', 'mac': self.env.generate_random_mac()},
            {'name': 'eth2', 'mac': self.env.generate_random_mac()},
            {'name': 'eth0', 'mac': self.env.generate_random_mac(),
                'ip': admin_ip},
            {'name': 'eth1', 'mac': self.env.generate_random_mac()}
        ]
        node = self.env.create_node(api=True, meta=meta,
                                    cluster_id=self.env.clusters[0].id)

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
        self.env.create_cluster(api=True)
        self.create_node_and_check_assignment()

    def test_neutron_gre_public_network_assigned_to_second_nic_by_name(self):
        self.env.create_cluster(api=True,
                                net_provider='neutron',
                                net_segment_type='gre')
        self.create_node_and_check_assignment()

    def test_neutron_vlan_public_network_assigned_to_second_nic_by_name(self):
        self.env.create_cluster(api=True,
                                net_provider='neutron',
                                net_segment_type='vlan')
        self.create_node_and_check_assignment()


class TestNodeNICsHandlersValidation(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeNICsHandlersValidation, self).setUp()
        self.env.create(
            cluster_kwargs={
                "net_provider": "neutron",
                "net_segment_type": "gre"
            },
            nodes_kwargs=[
                {"api": True, "pending_addition": True}
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
            self.assertEqual(resp.body, message)

    def test_assignment_change_failed_assigned_network_wo_id(self):
        self.nics_w_nets[0]["assigned_networks"] = [{}]

        self.node_nics_put_check_error(
            "Node '{0}', interface '{1}': each assigned network should "
            "have ID".format(
                self.env.nodes[0]["id"], self.nics_w_nets[0]['id']))

    def test_assignment_change_failed_node_has_unassigned_network(self):
        unassigned_id = self.nics_w_nets[0]["assigned_networks"][0]["id"]
        self.nics_w_nets[0]["assigned_networks"] = \
            self.nics_w_nets[0]["assigned_networks"][1:]

        self.node_nics_put_check_error(
            "Node '{0}': '{1}' network(s) are left unassigned".format(
                self.env.nodes[0]["id"], unassigned_id))

    def test_assignment_change_failed_node_has_unknown_network(self):
        self.nics_w_nets[0]["assigned_networks"].append({"id": 1234567})

        self.node_nics_put_check_error(
            "Network '1234567' doesn't exist for node {0}".format(
                self.env.nodes[0]["id"]))

    def test_nic_change_failed_node_has_unknown_interface(self):
        self.nics_w_nets[0]["id"] = 1234567

        self.node_nics_put_check_error(
            "Node '{0}': there is no interface with ID '1234567'"
            " in DB".format(self.env.nodes[0]["id"]))
