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

from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):

    def test_get_handler_with_wrong_nodeid(self):
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': 1}),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 404)

    def test_get_handler_with_invalid_data(self):
        meta = self.env.default_metadata()
        meta["interfaces"] = []
        node = self.env.create_node(api=True, meta=meta)
        meta_list = [
            {'interfaces': None},
            {'interfaces': {}}
        ]
        for nic_meta in meta_list:
            meta = self.env.default_metadata()
            meta.update(nic_meta)
            node_data = {'mac': node['mac'], 'meta': meta}
            resp = self.app.put(
                reverse('NodeAgentHandler'),
                jsonutils.dumps(node_data),
                expect_errors=True,
                headers=self.default_headers
            )
            self.assertEqual(resp.status_code, 400)
            resp = self.app.get(
                reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
                headers=self.default_headers
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json_body, [])

    def test_get_handler_with_incompleted_iface_data(self):
        meta = self.env.default_metadata()
        meta["interfaces"] = []
        node = self.env.create_node(api=True, meta=meta)
        meta_clean_list = [
            {'interfaces': [{'name': '', 'mac': '00:00:00:00:00:00'}]},
            {'interfaces': [{'mac': '00:00:00:00:00:00'}]},
            {'interfaces': [{'name': 'eth0'}]}
        ]

        for nic_meta in meta_clean_list:
            meta = self.env.default_metadata()
            meta.update(nic_meta)
            node_data = {'mac': node['mac'], 'meta': meta}
            resp = self.app.put(
                reverse('NodeAgentHandler'),
                jsonutils.dumps(node_data),
                expect_errors=True,
                headers=self.default_headers
            )
            self.assertEqual(resp.status_code, 200)
            resp = self.app.get(
                reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
                headers=self.default_headers
            )
            self.assertEqual(resp.json_body, [])

    def test_get_handler_with_invalid_speed_data(self):
        meta = self.env.default_metadata()
        meta["interfaces"] = []
        node = self.env.create_node(api=True, meta=meta)

        meta_clean_list = [
            {'interfaces': [{'name': 'eth0', 'mac': '00:00:00:00:00:00',
                             'max_speed': -100}]},
            {'interfaces': [{'name': 'eth0', 'mac': '00:00:00:00:00:00',
                             'current_speed': -100}]},
            {'interfaces': [{'name': 'eth0', 'mac': '00:00:00:00:00:00',
                             'current_speed': '100'}]},
            {'interfaces': [{'name': 'eth0', 'mac': '00:00:00:00:00:00',
                             'max_speed': 10.0}]},
            {'interfaces': [{'name': 'eth0', 'mac': '00:00:00:00:00:00',
                             'max_speed': '100'}]},
            {'interfaces': [{'name': 'eth0', 'mac': '00:00:00:00:00:00',
                             'current_speed': 10.0}]}
        ]
        for nic_meta in meta_clean_list:
            meta = self.env.default_metadata()
            meta.update(nic_meta)
            node_data = {'mac': node['mac'], 'meta': meta}
            resp = self.app.put(
                reverse('NodeAgentHandler'),
                jsonutils.dumps(node_data),
                expect_errors=True,
                headers=self.default_headers
            )
            self.assertEqual(resp.status_code, 200)
            resp = self.app.get(
                reverse('NodeHandler', kwargs={'obj_id': node['id']}),
                headers=self.default_headers
            )
            ifaces = resp.json_body['meta']['interfaces']
            self.assertEqual(
                ifaces,
                [
                    {'name': 'eth0', 'mac': '00:00:00:00:00:00',
                     'max_speed': None, 'current_speed': None}
                ]
            )

    def test_get_handler_without_NICs(self):
        meta = self.env.default_metadata()
        meta["interfaces"] = []
        node = self.env.create_node(api=True, meta=meta)
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json_body, [])

    def test_get_handler_with_NICs(self):
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': self.env.generate_random_mac(),
             'current_speed': 1, 'max_speed': 1},
            {'name': 'eth1', 'mac': self.env.generate_random_mac(),
             'current_speed': 1, 'max_speed': 1}])

        self.env.create_node(api=True, meta=meta)
        node_db = self.env.nodes[0]
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node_db.id}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertItemsEqual(
            map(lambda i: i['id'], resp.json_body),
            map(lambda i: i.id, node_db.interfaces)
        )
        for nic in meta['interfaces']:
            filtered_nics = filter(
                lambda i: i['mac'] == nic['mac'],
                resp.json_body
            )
            resp_nic = filtered_nics[0]
            self.assertEqual(resp_nic['mac'], nic['mac'])
            self.assertEqual(resp_nic['current_speed'], nic['current_speed'])
            self.assertEqual(resp_nic['max_speed'], nic['max_speed'])
            for conn in ('assigned_networks', ):
                self.assertEqual(resp_nic[conn], [])

    def test_nic_mac_swap(self):
        mac_eth0 = '00:11:22:dd:ee:ff'
        mac_eth1 = 'aa:bb:cc:33:44:55'

        eth0 = {
            'name': 'eth0',
            'mac': mac_eth0,
            'current_speed': 1,
            'state': 'up'
        }

        eth1 = {
            'name': 'eth1',
            'mac': mac_eth1,
            'current_speed': 1,
            'state': 'up'
        }

        # prepare metadata with our interfaces
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [eth0, eth1])

        # NOTE(prmtl) hack to have all mac set as we want
        # crete_node() will generate random mac for 1st iface
        # if we will not set it like that
        node_mac = meta['interfaces'][0]['mac']
        node = self.env.create_node(api=True, meta=meta, mac=node_mac)
        self.env.create_cluster(api=True, nodes=[node['id']])

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        original_nic_info = resp.json

        # swap macs, make them uppercase to check that we handle that correctly
        eth0['mac'], eth1['mac'] = eth1['mac'].upper(), eth0['mac'].upper()

        # update nodes with swapped macs
        new_meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(new_meta, [eth0, eth1])
        node_data = {'mac': node['mac'], 'meta': new_meta}
        self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(node_data),
            headers=self.default_headers)

        # check that networks are assigned to the same interfaces
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        updated_nic_info = resp.json

        for orig_iface in original_nic_info:
            updated_iface = next(
                iface for iface in updated_nic_info
                if iface['mac'] == orig_iface['mac'])

            self.assertEqual(
                orig_iface['assigned_networks'],
                orig_iface['assigned_networks'])
            # nic names were swapped
            self.assertNotEqual(orig_iface['name'], updated_iface['name'])

    def test_NIC_updates_by_agent(self):
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': '00:00:00:00:00:00', 'current_speed': 1,
             'state': 'up'}])
        node = self.env.create_node(api=True, meta=meta)
        new_meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(new_meta, [
            {'name': 'new_nic', 'mac': '00:00:00:00:00:00',
             'current_speed': 10, 'max_speed': 10, 'state': 'down'}])
        node_data = {'mac': node['mac'], 'meta': new_meta}
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(node_data),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 1)
        resp_nic = resp.json_body[0]
        nic = new_meta['interfaces'][0]
        self.assertEqual(resp_nic['mac'], nic['mac'])
        self.assertEqual(resp_nic['current_speed'], nic['current_speed'])
        self.assertEqual(resp_nic['max_speed'], nic['max_speed'])
        self.assertEqual(resp_nic['state'], nic['state'])
        for conn in ('assigned_networks', ):
            self.assertEqual(resp_nic[conn], [])

    def test_NIC_adds_by_agent(self):
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': '00:00:00:00:00:00', 'current_speed': 1,
             'state': 'up'}])
        node = self.env.create_node(api=True, meta=meta)

        meta['interfaces'].append({
            'name': 'new_nic', 'mac': '00:00:00:00:00:00'})
        node_data = {'mac': node['mac'], 'meta': meta}
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(node_data),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), len(meta['interfaces']))
        for nic in meta['interfaces']:
            filtered_nics = filter(
                lambda i: i['mac'] == nic['mac'],
                resp.json_body
            )
            resp_nic = filtered_nics[0]
            self.assertEqual(resp_nic['mac'], nic['mac'])
            self.assertEqual(resp_nic['current_speed'],
                             nic.get('current_speed'))
            self.assertEqual(resp_nic['max_speed'], nic.get('max_speed'))
            self.assertEqual(resp_nic['state'], nic.get('state'))
            for conn in ('assigned_networks', ):
                self.assertEqual(resp_nic[conn], [])

    def test_ignore_NIC_id_in_meta(self):
        fake_id = 'some_data'
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {'id': fake_id, 'name': 'eth0', 'mac': '12345'}])
        node = self.env.create_node(api=True, meta=meta)
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertNotEquals(resp.json_body[0]['id'], fake_id)

    def test_mac_address_should_be_in_lower_case(self):
        meta = self.env.default_metadata()
        new_mac = 'AA:BB:CC:DD:11:22'
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': new_mac}])
        node = self.env.create_node(api=True, meta=meta)
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertNotEquals(resp.json_body[0]['mac'], new_mac.lower())

    def test_remove_assigned_interface(self):
        def get_nodes():
            resp = self.app.get(
                reverse('NodeCollectionHandler',
                        kwargs={'cluster_id': self.env.clusters[0].id}),
                headers=self.default_headers,
            )
            return resp.json_body

        self.env.create(nodes_kwargs=[{'api': True}])

        # check all possible handlers
        for handler in ('NodeAgentHandler',
                        'NodeHandler',
                        'NodeCollectionHandler'):

            # create node and check it availability
            nodes_data = get_nodes()
            self.assertEqual(len(nodes_data), 1)

            # remove all interfaces except admin one
            adm_eth = self.env.network_manager._get_interface_by_network_name(
                nodes_data[0]['id'], 'fuelweb_admin')
            ifaces = list(nodes_data[0]['meta']['interfaces'])
            nodes_data[0]['meta']['interfaces'] = \
                [i for i in ifaces if i['name'] == adm_eth.name]

            # prepare put request
            data = {
                'id': nodes_data[0]['id'],
                'meta': nodes_data[0]['meta'],
            }
            if handler in ('NodeCollectionHandler', ):
                data = [data]

            if handler in ('NodeHandler', ):
                endpoint = reverse(handler, kwargs={'obj_id': data['id']})
            else:
                endpoint = reverse(handler)

            self.app.put(
                endpoint,
                jsonutils.dumps(data),
                headers=self.default_headers,
            )

            # check the node is visible for api
            nodes_data = get_nodes()
            self.assertEqual(len(nodes_data), 1)
            self.assertEqual(len(nodes_data[0]['meta']['interfaces']), 1)

            # restore removed interfaces
            nodes_data[0]['meta']['interfaces'] = ifaces
            self.app.put(
                reverse(
                    'NodeAgentHandler',
                ),
                jsonutils.dumps({
                    'id': nodes_data[0]['id'],
                    'meta': nodes_data[0]['meta'],
                }),
                headers=self.default_headers,
            )

            # check node availability
            nodes_data = get_nodes()
            self.assertEqual(len(nodes_data), 1)
            self.assertItemsEqual(nodes_data[0]['meta']['interfaces'], ifaces)

    def test_change_mac_of_assigned_nics(self):
        def get_nodes():
            resp = self.app.get(
                reverse('NodeCollectionHandler',
                        kwargs={'cluster_id': self.env.clusters[0].id}),
                headers=self.default_headers,
            )
            return resp.json_body

        meta = self.env.default_metadata()
        meta["interfaces"] = [
            {'name': 'eth0', 'mac': self.env.generate_random_mac()},
            {'name': 'eth1', 'mac': self.env.generate_random_mac()},
            {'name': 'eth2', 'mac': self.env.generate_random_mac()},
            {'name': 'eth3', 'mac': self.env.generate_random_mac()},
            {'name': 'eth4', 'mac': self.env.generate_random_mac()},
        ]
        self.env.create(nodes_kwargs=[{'api': True, 'meta': meta}])

        # check all possible handlers
        for handler in ('NodeAgentHandler',
                        'NodeHandler',
                        'NodeCollectionHandler'):

            # create node and check it availability
            nodes_data = get_nodes()
            self.assertEqual(len(nodes_data), 1)

            # change mac address of interfaces except admin one
            adm_eth = self.env.network_manager._get_interface_by_network_name(
                nodes_data[0]['id'], 'fuelweb_admin')
            for iface in nodes_data[0]['meta']['interfaces']:
                if iface['name'] != adm_eth.name:
                    iface['mac'] = self.env.generate_random_mac()

            # prepare put request
            data = {
                'id': nodes_data[0]['id'],
                'meta': nodes_data[0]['meta'],
            }
            if handler in ('NodeCollectionHandler', ):
                data = [data]

            if handler in ('NodeHandler', ):
                endpoint = reverse(handler, kwargs={'obj_id': data['id']})
            else:
                endpoint = reverse(handler)

            self.app.put(
                endpoint,
                jsonutils.dumps(data),
                headers=self.default_headers,
            )

            # check the node is visible for api
            nodes_data = get_nodes()
            self.assertEqual(len(nodes_data), 1)
