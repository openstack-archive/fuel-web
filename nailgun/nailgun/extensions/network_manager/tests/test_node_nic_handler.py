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

from mock import patch
import uuid

from copy import deepcopy
from oslo_serialization import jsonutils

from nailgun import consts
from nailgun import objects

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


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

    @patch.dict('nailgun.api.v1.handlers.version.settings.VERSION', {
        'release': '5.0'})
    def test_get_handler_with_NICs_before_61(self):
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
            self.assertNotIn('interface_properties', resp_nic)

    def test_nic_mac_swap(self):
        mac_eth0 = '00:11:22:dd:ee:ff'
        mac_eth1 = 'aa:bb:cc:33:44:55'

        eth0 = {
            'name': 'eth0',
            'mac': mac_eth0,
            'current_speed': 1,
            'state': 'up',
            'pxe': True
        }

        eth1 = {
            'name': 'eth1',
            'mac': mac_eth1,
            'current_speed': 1,
            'state': 'up',
            'pxe': False
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
        self.env.set_interfaces_in_meta(meta, [{
            'name': 'eth0',
            'mac': '00:00:00:00:00:00',
            'current_speed': 1,
            'state': 'up'}
        ])

        node = self.env.create_node(api=True, meta=meta)
        new_meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(new_meta, [
            {'name': 'new_nic',
             'mac': '00:00:00:00:00:00',
             'current_speed': 10,
             'max_speed': 10,
             'state': 'down',
             'interface_properties': {
                 'sriov': {
                     'sriov_totalvfs': 8,
                     'available': True,
                     'pci_id': '1234:5678'
                 },
                 'pci_id': '8765:4321',
                 'numa_node': 1
             }}]
        )
        node_data = {'mac': node['mac'], 'meta': new_meta, 'is_agent': True}
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(node_data),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        # add node into cluster
        self.env.create_cluster(nodes=[node['id']])
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
        self.assertEqual(
            resp_nic['attributes']['sriov'],
            {
                'metadata': {
                    'label': 'SRIOV',
                    'weight': 30
                },
                'sriov_enabled': {
                    'label': 'SRIOV enabled',
                    'weight': 10,
                    'type': 'checkbox',
                    'value': False
                },
                'sriov_numvfs': {
                    'label': 'Virtual functions',
                    'weight': 20,
                    'type': 'number',
                    'min': 0,
                    'max': 8,
                    'value': None
                },
                'physnet': {
                    'label': 'Physical network',
                    'weight': 30,
                    'type': 'text',
                    'value': 'physnet2'
                }
            })
        self.assertEqual(
            resp_nic['meta']['sriov'],
            {
                'available': True,
                'pci_id': '1234:5678',
                'sriov_totalvfs': 8
            })

        self.assertEqual(
            resp_nic['attributes']['dpdk'],
            {
                'metadata': {
                    'label': 'DPDK',
                    'weight': 40
                },
                'dpdk_enabled': {
                    'label': 'DPDK enabled',
                    'weight': 10,
                    'type': 'checkbox',
                    'value': False
                }
            })
        self.assertEqual(
            resp_nic['meta']['dpdk'], {'available': False})

    def create_cluster_and_node_with_dpdk_support(self, segment_type,
                                                  drivers_mock):
        drivers_mock.return_value = {
            'driver_1': ['8765:4321']
        }
        cluster = self.env.create_cluster(net_segment_type=segment_type)
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': '00:00:00:00:00:00', 'current_speed': 1,
             'state': 'up'}])
        node = self.env.create_node(api=True, meta=meta,
                                    cluster_id=cluster['id'])
        new_meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(new_meta, [
            {'name': 'eth0',
             'mac': '00:00:00:00:00:00',
             'current_speed': 10,
             'max_speed': 10,
             'state': 'up',
             'interface_properties': {
                 'pci_id': '8765:4321',
                 'numa_node': 1
             }}]
        )
        node_data = {'mac': node['mac'], 'meta': new_meta, 'is_agent': True}
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(node_data),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        return node

    def check_update_dpdk_availability(self, node, dpdk_available):
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 1)
        resp_nic = resp.json_body[0]
        self.assertEqual(
            resp_nic['attributes']['dpdk'],
            {
                'metadata': {
                    'label': 'DPDK',
                    'weight': 40
                },
                'dpdk_enabled': {
                    'label': 'DPDK enabled',
                    'weight': 10,
                    'type': 'checkbox',
                    'value': False
                }
            })
        self.assertEqual(
            resp_nic['meta']['dpdk'], {'available': dpdk_available})
        return resp.json_body

    def check_put_request_passes_without_dpdk_section(self, node, nics):
        # remove 'dpdk' section from all interfaces
        for nic in nics:
            nic['attributes'].pop('dpdk', None)
        resp = self.app.put(
            reverse("NodeNICsHandler", kwargs={"node_id": node['id']}),
            jsonutils.dumps(nics),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

    @patch('nailgun.objects.Release.get_supported_dpdk_drivers')
    def test_update_dpdk_unavailable_tun(self, drivers_mock):
        node = self.create_cluster_and_node_with_dpdk_support(
            consts.NEUTRON_SEGMENT_TYPES.tun, drivers_mock)
        nics = self.check_update_dpdk_availability(node, False)
        self.check_put_request_passes_without_dpdk_section(node, nics)

    @patch('nailgun.objects.Release.get_supported_dpdk_drivers')
    def test_update_dpdk_available_vlan(self, drivers_mock):
        node = self.create_cluster_and_node_with_dpdk_support(
            consts.NEUTRON_SEGMENT_TYPES.vlan, drivers_mock)
        nics = self.check_update_dpdk_availability(node, True)
        self.check_put_request_passes_without_dpdk_section(node, nics)

    def test_NIC_offloading_modes(self):
        meta = self.env.default_metadata()
        meta["interfaces"] = []
        node = self.env.create_node(api=True, meta=meta)
        new_meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(new_meta, [
            {'name': 'new_nic',
             'mac': '00:00:00:00:00:00',
             'offloading_modes': [
                 {
                     'name': 'mode_1',
                     'state': True,
                     "sub": []
                 },
                 {
                     'name': 'mode_2',
                     'state': False,
                     "sub": []
                 },
                 {
                     'name': 'mode_3',
                     'state': None,
                     "sub": []
                 }
             ]}])
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
        self.assertEqual(resp_nic['offloading_modes'], nic['offloading_modes'])

    def test_NIC_change_offloading_modes(self):
        meta = self.env.default_metadata()
        meta["interfaces"] = []
        node = self.env.create_node(api=True, meta=meta)
        new_meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(new_meta, [
            {'name': 'new_nic',
             'mac': '00:00:00:00:00:00',
             'offloading_modes': [
                 {
                     'name': 'mode_1',
                     'state': None,
                     "sub": []
                 },
                 {
                     'name': 'mode_2',
                     'state': None,
                     "sub": []
                 },
                 {
                     'name': 'mode_3',
                     'state': None,
                     "sub": []
                 }
             ]}])
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
        self.assertEqual(resp_nic['offloading_modes'], nic['offloading_modes'])

        resp = self.app.get(
            reverse('NodeCollectionHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 1)

        resp_node = resp.json_body[0]
        new_nic = {
            'name': 'new_nic',
            'mac': '00:00:00:00:00:00',
            'offloading_modes': [
                {
                    'name': 'mode_1',
                    'state': True,
                    "sub": []
                },
                {
                    'name': 'mode_2',
                    'state': False,
                    "sub": []
                },
                {
                    'name': 'mode_3',
                    'state': None,
                    "sub": []
                }
            ]
        }
        self.env.set_interfaces_in_meta(resp_node["meta"], [
            new_nic])

        resp_node.pop('group_id')

        resp = self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([resp_node]),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 1)
        resp_nic = resp.json_body[0]
        self.assertEqual(
            resp_nic['offloading_modes'],
            new_nic['offloading_modes'])

    def test_NIC_locking_on_update_by_agent(self):
        lock_vs_status = (
            (consts.NODE_STATUSES.discover, False),
            (consts.NODE_STATUSES.error, True, consts.NODE_ERRORS.deletion),
            (consts.NODE_STATUSES.error, True, consts.NODE_ERRORS.deploy),
            (consts.NODE_STATUSES.error, False, consts.NODE_ERRORS.discover),
            (consts.NODE_STATUSES.error, True, consts.NODE_ERRORS.provision),
            (consts.NODE_STATUSES.error, True,
             consts.NODE_ERRORS.stop_deployment),
            (consts.NODE_STATUSES.provisioning, True),
            (consts.NODE_STATUSES.provisioned, True),
            (consts.NODE_STATUSES.stopped, True),
            (consts.NODE_STATUSES.deploying, True),
            (consts.NODE_STATUSES.ready, True),
            (consts.NODE_STATUSES.removing, True))

        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': '00:00:00:00:00:00', 'current_speed': 1,
             'state': 'up', 'pxe': True}])
        self.env.create_node(api=True, meta=meta)
        new_meta = deepcopy(meta)
        node = self.env.nodes[0]

        for case in lock_vs_status:
            node.status = case[0]
            if node.status == consts.NODE_STATUSES.error:
                node.error_type = case[2]
            self.db.flush()
            lock = case[1]

            new_meta['interfaces'][0]['current_speed'] += 1
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
            resp_nic = resp.json_body[0]
            new_speed = new_meta['interfaces'][0]['current_speed']
            old_speed = meta['interfaces'][0]['current_speed']
            self.assertEqual(resp_nic['current_speed'],
                             old_speed if lock else new_speed)
            meta['interfaces'][0]['current_speed'] = resp_nic['current_speed']

    @patch.dict('nailgun.api.v1.handlers.version.settings.VERSION', {
        'release': '6.1'})
    def test_interface_properties_after_update_by_agent(self):
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': '00:00:00:00:00:00', 'current_speed': 1,
             'pxe': True, 'state': 'up'}])
        self.env.create(
            nodes_kwargs=[
                {"api": True, 'meta': meta}
            ]
        )
        node = self.env.nodes[0]
        node_data = {'mac': node['mac'], 'meta': meta}
        # check default interface_properties values
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        nic = resp.json_body[0]

        # change mtu
        nic['attributes']['mtu'] = {
            'metadata': {
                'label': 'MTU',
                'weight': 20
            },
            'mtu_value': {
                'label': 'MTU',
                'weight': 10,
                'type': 'text',
                'value': 1500
            }
        }
        nodes_list = [{'id': node['id'], 'interfaces': [nic]}]
        resp_put = self.app.put(
            reverse('NodeCollectionNICsHandler'),
            jsonutils.dumps(nodes_list),
            headers=self.default_headers
        )
        self.assertEqual(resp_put.status_code, 200)
        # update NICs by agent (no interface_properties values provided)
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(node_data),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        # check interface_properties values were not reset to default
        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        resp_nic = resp.json_body[0]
        self.assertEqual(resp_nic['attributes']['mtu'], {
            'metadata': {
                'label': 'MTU',
                'weight': 20
            },
            'mtu_value': {
                'label': 'MTU',
                'weight': 10,
                'type': 'text',
                'value': 1500
            }
        })

    def test_nic_adds_by_agent(self):
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': '00:00:00:00:00:00', 'current_speed': 1,
             'pxe': True, 'state': 'up'}])
        node = self.env.create_node(api=True, meta=meta)

        meta['interfaces'].append({
            'name': 'new_nic', 'mac': '00:00:00:00:00:01'})
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
                        kwargs={'cluster_id': cluster.id}),
                headers=self.default_headers,
            )
            return resp.json_body

        cluster = self.env.create(nodes_kwargs=[{'api': True}])

        # check all possible handlers
        for handler in ('NodeAgentHandler',
                        'NodeHandler',
                        'NodeCollectionHandler'):

            # create node and check it availability
            nodes_data = get_nodes()
            self.assertEqual(len(nodes_data), 1)

            node_db = objects.Node.get_by_uid(nodes_data[0]['id'])

            # remove all interfaces except admin one
            adm_eth = self.env.network_manager._get_interface_by_network_name(
                node_db, 'fuelweb_admin')
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
                        kwargs={'cluster_id': cluster.id}),
                headers=self.default_headers,
            )
            return resp.json_body

        meta = self.env.default_metadata()
        meta["interfaces"] = [
            {'name': 'eth0', 'mac': self.env.generate_random_mac(),
             'pxe': True},
            {'name': 'eth1', 'mac': self.env.generate_random_mac()},
            {'name': 'eth2', 'mac': self.env.generate_random_mac()},
            {'name': 'eth3', 'mac': self.env.generate_random_mac()},
            {'name': 'eth4', 'mac': self.env.generate_random_mac()},
        ]
        cluster = self.env.create(nodes_kwargs=[{'api': True, 'meta': meta}])

        # check all possible handlers
        for handler in ('NodeAgentHandler',
                        'NodeHandler',
                        'NodeCollectionHandler'):

            # create node and check it availability
            nodes_data = get_nodes()
            self.assertEqual(len(nodes_data), 1)

            node_db = objects.Node.get_by_uid(nodes_data[0]['id'])

            # change mac address of interfaces except admin one
            adm_eth = self.env.network_manager._get_interface_by_network_name(
                node_db, 'fuelweb_admin')
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

    def test_pxe_for_admin_nws_restriction(self):
        meta = self.env.default_metadata()
        # We are using reverse ordered by iface name list
        # for reproducing bug #1474330
        meta['interfaces'] = [
            {'name': 'eth1', 'mac': self.env.generate_random_mac(),
             'pxe': False},
            {'name': 'eth0', 'mac': self.env.generate_random_mac(),
             'pxe': False},
        ]
        cluster = self.env.create(nodes_kwargs=[{'api': False, 'meta': meta}])

        node = cluster.nodes[0]

        # Processing data through NodeHandler
        resp = self.app.get(
            reverse('NodeHandler', kwargs={'obj_id': node.id}),
            headers=self.default_headers,
        )
        data = resp.json_body

        resp = self.app.put(
            reverse('NodeHandler', kwargs={'obj_id': data['id']}),
            jsonutils.dumps(data),
            headers=self.default_headers,
        )
        self.assertEqual(resp.status_code, 200)

        # Processing data through NICsHander
        resp = self.app.get(
            reverse("NodeNICsHandler", kwargs={"node_id": node.id}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json_body

        resp = self.app.put(
            reverse("NodeNICsHandler", kwargs={"node_id": node.id}),
            jsonutils.dumps(data),
            headers=self.default_headers,
        )
        self.assertEqual(resp.status_code, 200)

    def test_public_network_assigment_to_wrong_node(self):
        cluster = self.env.create(api=True)
        node = self.env.create_node(
            api=True,
            cluster_id=cluster.id,
            roles=['controller'])
        resp = self.app.get(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": node['id']}))

        networks = resp.json[1]['assigned_networks']
        compute = self.env.create_node(
            api=True,
            cluster_id=cluster.id,
            roles=['compute'])

        resp = self.app.get(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": compute['id']}))

        data = resp.json
        data[1]['assigned_networks'] = networks

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": compute['id']}),
            jsonutils.dumps(data),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 400)
        message = jsonutils.loads(resp.body)['message']
        self.assertEqual(
            message,
            'Trying to assign public network to Node \'%d\' which should '
            'not have public network' % compute['id'])


class TestSriovHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestSriovHandlers, self).setUp()
        cluster = self.env.create_cluster(
            editable_attributes={
                'common': {
                    'libvirt_type': {
                        'value': consts.HYPERVISORS.kvm
                    }
                }
            }
        )
        self.env.create_nodes_w_interfaces_count(
            1, 3, cluster_id=cluster.id, api=True)
        self.nics = self.get_node_interfaces()

    def get_node_interfaces(self):
        resp = self.app.get(
            reverse('NodeNICsHandler',
                    kwargs={'node_id': self.env.nodes[0].id}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        return resp.json_body

    def test_get_update_sriov_properties(self):
        # Use NIC #2 as SR-IOV can be enabled only on NICs that have no
        # assigned networks. First two NICs have assigned networks.

        # change NIC properties in DB as SR-IOV parameters can be set up only
        # for NICs that have hardware SR-IOV support
        nic = self.env.nodes[0].nic_interfaces[2]
        nic.meta['sriov']['available'] = True
        nic.meta['sriov']['sriov_totalvfs'] = 8
        nic.meta.changed()

        nics = self.get_node_interfaces()
        sriov = nics[2]['attributes']['sriov']
        sriov['sriov_enabled']['value'] = True
        sriov['sriov_numvfs']['value'] = 8
        sriov['physnet']['value'] = 'new_physnet'

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0].id}),
            jsonutils.dumps(nics),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        sriov = resp.json_body[2]['attributes']['sriov']
        self.assertEqual(sriov['sriov_enabled']['value'], True)
        self.assertEqual(sriov['sriov_numvfs']['value'], 8)
        self.assertEqual(sriov['physnet']['value'], 'new_physnet')

    def test_update_readonly_sriov_properties_failed(self):
        self.nics[0]['meta']['sriov']['available'] = True

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0].id}),
            jsonutils.dumps(self.nics),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body['message'],
            "Node '{0}' interface '{1}': SR-IOV parameter 'available' cannot "
            "be changed through API".format(
                self.env.nodes[0].id, self.nics[0]['name']))

    def test_enable_sriov_failed_when_not_available(self):
        self.nics[0]['attributes']['sriov']['sriov_enabled']['value'] = True

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0].id}),
            jsonutils.dumps(self.nics),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body['message'],
            "Node '{0}' interface '{1}': SR-IOV cannot be enabled as it is"
            " not available".format(
                self.env.nodes[0].id, self.nics[0]['name']))

    def test_set_sriov_numvfs_failed(self):
        self.nics[0]['attributes']['sriov']['sriov_numvfs']['value'] = 8

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0].id}),
            jsonutils.dumps(self.nics),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body['message'],
            "Node '{0}' interface '{1}': '8' virtual functions was "
            "requested but just '0' are available".format(
                self.env.nodes[0].id, self.nics[0]['name']))

    def test_set_sriov_numvfs_failed_negative_value(self):
        self.nics[0]['attributes']['sriov']['sriov_numvfs']['value'] = -40

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0].id}),
            jsonutils.dumps(self.nics),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            "-40 is not valid under any of the given schemas",
            resp.json_body['message']
        )

    def test_set_sriov_numvfs_failed_float_value(self):
        self.nics[0]['attributes']['sriov']['sriov_numvfs']['value'] = 2.5

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0].id}),
            jsonutils.dumps(self.nics),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            "2.5 is not valid under any of the given schemas",
            resp.json_body['message']
        )

    def test_set_sriov_numvfs_zero_value(self):
        self.nics[0]['attributes']['sriov']['sriov_numvfs']['value'] = 0

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0].id}),
            jsonutils.dumps(self.nics),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            "0 is not valid under any of the given schemas",
            resp.json_body['message']
        )

    def test_enable_sriov_without_number_of_functions(self):
        # change NIC properties in DB as SR-IOV parameters can be set up only
        # for NICs that have hardware SR-IOV support
        nic = objects.NIC.get_by_uid(self.env.nodes[0].nic_interfaces[0].id)
        nic.meta['sriov']['available'] = True
        nic.meta['sriov']['sriov_totalvfs'] = 8
        nic.meta.changed()

        nics = self.get_node_interfaces()
        nics[0]['attributes']['sriov']['sriov_enabled']['value'] = True

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0].id}),
            jsonutils.dumps(nics),
            expect_errors=True,
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 400)
        self.assertIn(
            "Node '{0}' interface '{1}': virtual functions can not be"
            " enabled for interface when 'sriov_numfs' option is not"
            " specified!".format(self.env.nodes[0].id,
                                 self.env.nodes[0].nic_interfaces[0].name),
            resp.json_body['message']
        )

    def test_enable_sriov_failed_with_non_kvm_hypervisor(self):
        node = self.env.create_node(api=True, roles=['compute'])
        self.env.create_cluster(
            api=True,
            nodes=[node['id']],
            editable_attributes={
                'common': {
                    'libvirt_type': {
                        'value': consts.HYPERVISORS.qemu
                    }
                }
            }
        )

        resp = self.app.get(
            reverse('NodeNICsHandler',
                    kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        nics = resp.json_body
        nics[0]['attributes']['sriov']['sriov_enabled']['value'] = True

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": node['id']}),
            jsonutils.dumps(nics),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            "Only KVM hypervisor works with SR-IOV.",
            resp.json_body['message']
        )

    def test_enable_sriov_failed_when_nic_has_networks_assigned(self):
        nic = self.env.nodes[0].nic_interfaces[0]
        nic.meta['sriov']['available'] = True
        nic.meta['sriov']['sriov_totalvfs'] = 8
        nic.meta.changed()

        nics = self.get_node_interfaces()
        nics[0]['attributes']['sriov']['sriov_enabled']['value'] = True
        nics[0]['attributes']['sriov']['sriov_numvfs']['value'] = 8

        resp = self.app.put(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0].id}),
            jsonutils.dumps(nics),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body['message'],
            "Node '{0}' interface '{1}': SR-IOV cannot be enabled when "
            "networks are assigned to the interface".format(
                self.env.nodes[0].id, nics[0]['name']))


class TestNICAttributesHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestNICAttributesHandlers, self).setUp()
        self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.multinode},
            release_kwargs={
                'name': uuid.uuid4().get_hex(),
                'version': 'newton-10.0',
                'operating_system': 'Ubuntu',
                'modes': [consts.CLUSTER_MODES.multinode,
                          consts.CLUSTER_MODES.ha_compact]},
            nodes_kwargs=[{'roles': ['controller']}])
        self.node = self.env.nodes[0]

    def test_get_nic_attributes(self):
        resp = self.app.get(
            reverse("NodeNICsHandler", kwargs={"node_id": self.node.id}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        expected_attributes = {
            'offloading': {
                'disable_offloading': {
                    'value': False,
                    'label': 'Disable offloading',
                    'type': 'checkbox',
                    'weight': 10
                },
                'metadata': {
                    'label': 'Offloading',
                    'weight': 10
                },
                'offloading_modes': {
                    'description': 'Offloading modes',
                    'value': {},
                    'label': 'Offloading modes',
                    'type': 'offloading_modes',
                    'weight': 20
                }
            },
            'mtu': {
                'mtu_value': {
                    'value': None,
                    'label': 'MTU',
                    'type': 'text',
                    'weight': 10
                },
                'metadata': {
                    'label': 'MTU',
                    'weight': 20
                }
            },
            'sriov': {
                'sriov_enabled': {
                    'value': False,
                    'label': 'SRIOV enabled',
                    'type': 'checkbox',
                    'weight': 10
                },
                'physnet': {
                    'value': 'physnet2',
                    'label': 'Physical network',
                    'type': 'text',
                    'weight': 30
                },
                'metadata': {
                    'label': 'SRIOV',
                    'weight': 30
                },
                'sriov_numvfs': {
                    'max': 0,
                    'value': None,
                    'label': 'Virtual functions',
                    'weight': 20,
                    'type': 'number',
                    'min': 0
                },
            },
            'dpdk': {
                'dpdk_enabled': {
                    'value': False,
                    'label': 'DPDK enabled',
                    'type': 'checkbox',
                    'weight': 10
                },
                'metadata': {
                    'label': 'DPDK',
                    'weight': 40
                }
            }
        }

        for interface in resp.json_body:
            self.assertEqual(expected_attributes, interface['attributes'])

    def test_put_nic_attributes(self):
        pass
