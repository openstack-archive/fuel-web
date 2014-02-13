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

from nailgun.consts import NETWORK_INTERFACE_TYPES
from nailgun.consts import OVS_BOND_MODES
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestNodeNICsBonding(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeNICsBonding, self).setUp()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {"name": "eth0", "mac": "00:00:00:00:00:66"},
            {"name": "eth1", "mac": "00:00:00:00:00:77"},
            {"name": "eth2", "mac": "00:00:00:00:00:88"}])
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

        resp = self.app.get(
            reverse('NodeNICsHandler',
                    kwargs={'node_id': self.env.nodes[0]['id']}),
            headers=self.default_headers)
        self.assertEquals(resp.status, 200)
        self.data = json.loads(resp.body)
        self.admin_nic, self.other_nic, self.empty_nic = None, None, None
        for nic in self.data:
            net_names = [n['name'] for n in nic['assigned_networks']]
            if 'fuelweb_admin' in net_names:
                self.admin_nic = nic
            elif net_names:
                self.other_nic = nic
            else:
                self.empty_nic = nic
        self.assertTrue(self.admin_nic and self.other_nic and self.empty_nic)

    def node_nics_put_check_error(self, message):
        resp = self.env.node_nics_put(self.env.nodes[0]['id'], self.data,
                                      expect_errors=True)
        self.assertEquals(resp.status, 400)
        self.assertEquals(resp.body, message)

    def nics_bond_create(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {'id': self.other_nic['id']},
                {'id': self.empty_nic['id']},
            ],
            "assigned_networks": self.other_nic['assigned_networks']
        })
        self.other_nic['assigned_networks'] = []

        resp = self.env.node_nics_put(self.env.nodes[0]['id'], self.data)
        self.assertEquals(resp.status, 200)

        resp = self.env.node_nics_get(self.env.nodes[0]['id'])
        self.assertEquals(resp.status, 200)
        data = json.loads(resp.body)
        for nic in data:
            if nic['type'] == NETWORK_INTERFACE_TYPES.bond:
                self.assertEqual(nic['name'], "ovs-bond0")
                self.assertTrue('id' in nic)

    def test_nics_bond_remove(self):
        self.nics_bond_create()

        resp = self.env.node_nics_get(self.env.nodes[0]['id'])
        self.assertEquals(resp.status, 200)
        data = json.loads(resp.body)
        for nic in data:
            if nic['type'] == NETWORK_INTERFACE_TYPES.bond:
                bond = nic
                break
        else:
            raise Exception("No bond was found unexpectedly")
        data.remove(bond)
        for nic in data:
            if nic['id'] == bond['slaves'][0]['id']:
                nic['assigned_networks'] = bond['assigned_networks']
                break
        else:
            raise Exception("NIC from bond wasn't found unexpectedly")

        resp = self.env.node_nics_put(self.env.nodes[0]['id'], data)
        self.assertEquals(resp.status, 200)

        resp = self.env.node_nics_get(self.env.nodes[0]['id'])
        self.assertEquals(resp.status, 200)
        data = json.loads(resp.body)
        for nic in data:
            self.assertNotEqual(nic['type'], NETWORK_INTERFACE_TYPES.bond)

    def test_nics_bond_create_failed_no_type(self):
        self.data.append({
            "name": "ovs-bond0"
        })

        self.node_nics_put_check_error(
            "Node '%d': each interface must have a "
            "type" % self.env.nodes[0]['id'])

    def test_nics_bond_create_failed_not_have_enough_data(self):
        self.data.append({
            "type": NETWORK_INTERFACE_TYPES.bond
        })
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d': each bond interface must have "
            "either ID or name" % self.env.nodes[0]['id'])

    def test_nics_bond_create_failed_unknown_mode(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": "unknown",
            "slaves": [
                {'id': self.other_nic['id']},
                {'id': self.empty_nic['id']}],
            "assigned_networks": self.other_nic['assigned_networks']
        })
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d': bond interface has unknown mode "
            "'unknown'" % self.env.nodes[0]['id'])

    def test_nics_bond_create_failed_no_mode(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "slaves": [
                {'id': self.other_nic['id']},
                {'id': self.empty_nic['id']}],
            "assigned_networks": self.other_nic['assigned_networks']
        })
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d': each bond interface must have "
            "mode" % self.env.nodes[0]['id'])

    def test_nics_bond_create_failed_no_slaves(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "assigned_networks": self.other_nic['assigned_networks']
        })
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d': each bond interface must have "
            "two or more slaves" % self.env.nodes[0]['id'])

    def test_nics_bond_create_failed_one_slave(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {'id': self.other_nic['id']}],
            "assigned_networks": self.other_nic['assigned_networks']
        })
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d': each bond interface must have "
            "two or more slaves" % self.env.nodes[0]['id'])

    def test_nics_bond_create_failed_no_assigned_networks(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {'id': self.other_nic['id']},
                {'id': self.empty_nic['id']}],
        })
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d', interface 'ovs-bond0': there is no "
            "'assigned_networks' list" % self.env.nodes[0]['id'])

    def test_nics_bond_create_failed_nic_is_used_twice(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {'id': self.other_nic['id']},
                {'id': self.other_nic['id']}],
            "assigned_networks": self.other_nic['assigned_networks']
        })
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d': interface '%d' is used in bonds more "
            "than once" % (self.env.nodes[0]['id'], self.other_nic['id']))

    def test_nics_bond_create_failed_duplicated_assigned_networks(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {'id': self.other_nic['id']},
                {'id': self.empty_nic['id']}],
            "assigned_networks": self.other_nic['assigned_networks']
        })

        self.node_nics_put_check_error(
            "Node '%d': there is a duplicated network '%d' in "
            "assigned networks (second occurrence is in interface "
            "'ovs-bond0')" % (self.env.nodes[0]['id'],
                              self.other_nic['assigned_networks'][0]['id']))

    def test_nics_bond_create_failed_unknown_interface(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {'id': self.other_nic['id']},
                {'id': 1234567}],
            "assigned_networks": self.other_nic['assigned_networks']
        })
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d': there is no interface '1234567' found for bond "
            "'ovs-bond0' in DB" % self.env.nodes[0]['id'])

    def test_nics_bond_create_failed_slave_has_assigned_networks(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {'id': self.other_nic['id']},
                {'id': self.empty_nic['id']}],
            "assigned_networks": []
        })

        self.node_nics_put_check_error(
            "Node '%d': interface '%d' cannot have assigned networks as it is "
            "used in bond" % (self.env.nodes[0]['id'], self.other_nic['id']))

    def test_nics_bond_create_failed_slave_has_no_id(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {'id': self.other_nic['id']},
                {'nic': self.empty_nic['id']}],
            "assigned_networks": self.other_nic['assigned_networks']
        })
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d', interface 'ovs-bond0': each bond slave "
            "must have either ID or Name" % self.env.nodes[0]['id'])

    def test_nics_bond_create_failed_assigned_network_wo_id(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {'id': self.other_nic['id']},
                {'id': self.empty_nic['id']}],
            "assigned_networks": [{}]
        })
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d', interface 'ovs-bond0': each assigned network should "
            "have ID" % self.env.nodes[0]['id'])

    def test_nics_bond_create_failed_node_has_unassigned_network(self):
        self.data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {'id': self.other_nic['id']},
                {'id': self.empty_nic['id']}],
            "assigned_networks": self.other_nic['assigned_networks'][1:]
        })
        unassigned_id = self.other_nic['assigned_networks'][0]['id']
        self.other_nic['assigned_networks'] = []

        self.node_nics_put_check_error(
            "Node '%d': '%d' network(s) are left unassigned" % (
                self.env.nodes[0]['id'], unassigned_id))
