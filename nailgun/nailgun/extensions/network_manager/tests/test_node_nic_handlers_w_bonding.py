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

import mock
import uuid

from oslo_serialization import jsonutils

from nailgun.consts import BOND_MODES
from nailgun.consts import BOND_TYPES
from nailgun.consts import BOND_XMIT_HASH_POLICY
from nailgun.consts import CLUSTER_MODES
from nailgun.consts import HYPERVISORS
from nailgun.consts import NETWORK_INTERFACE_TYPES
from nailgun.db import db
from nailgun.extensions.network_manager.validators import network
from nailgun import objects
from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestNodeNICsBonding(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeNICsBonding, self).setUp()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [
            {"name": "eth0",
             "mac": "00:00:00:00:00:66",
             "pxe": True,
             "offloading_modes": [
                 {
                     "name": "mode_1",
                     "state": None,
                     "sub": []
                 },
                 {
                     "name": "mode_common",
                     "state": None,
                     "sub": []
                 }
             ]
             },
            {"name": "eth1",
             "mac": "00:00:00:00:00:77",
             "offloading_modes": [
                 {
                     "name": "mode_2",
                     "state": None,
                     "sub": []
                 },
                 {
                     "name": "mode_common",
                     "state": None,
                     "sub": []
                 }
             ]
             },
            {"name": "eth2",
             "mac": "00:00:00:00:00:88",
             "offloading_modes": [
                 {
                     "name": "mode_3",
                     "state": None,
                     "sub": []
                 },
                 {
                     "name": "mode_4",
                     "state": None,
                     "sub": []
                 },
                 {
                     "name": "mode_common",
                     "state": None,
                     "sub": []
                 }
             ]},
            {"name": "eth3",
             "mac": "00:00:00:00:00:99",
             'interface_properties': {
                 'sriov': {
                     'sriov_totalvfs': 8,
                     'available': True,
                     'pci_id': '1234:5678'
                 }
             }}
        ])

        self.cluster = self.env.create(
            cluster_kwargs={
                "net_provider": "neutron",
                "net_segment_type": "gre"
            },
            nodes_kwargs=[
                {"api": True,
                 "pending_addition": True,
                 "meta": meta}
            ]
        )
        self.get_node_nics_info()

    def get_node_nics_info(self):
        resp = self.app.get(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0]["id"]}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.data = resp.json_body
        self.admin_nic, self.other_nic, self.empty_nic = None, None, None
        self.sriov_nic = None
        for nic in self.data:
            net_names = [n["name"] for n in nic["assigned_networks"]]
            if "fuelweb_admin" in net_names:
                self.admin_nic = nic
            elif net_names:
                self.other_nic = nic
            elif nic['meta']['sriov']['available']:
                self.sriov_nic = nic
            else:
                self.empty_nic = nic
        self.assertTrue(self.admin_nic and self.other_nic and
                        self.empty_nic and self.sriov_nic)

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

    def nics_bond_create_and_check(self, put_func):
        bond_name = 'bond0'
        self.prepare_bond_w_props(bond_name=bond_name)
        self.check_bond_creation(put_func, bond_name=bond_name)

    def prepare_bond_w_props(self, bond_name='bond0',
                             bond_type=BOND_TYPES.linux,
                             bond_mode=BOND_MODES.l_802_3ad,
                             iface_props=None):
        if iface_props is None:
            iface_props = {}

        attributes = {
            'mode': {'value': {'value': bond_mode}},
            'xmit_hash_policy': {
                'value': {'value': BOND_XMIT_HASH_POLICY.layer2_3}},
            'lacp_rate': {'value': {'value': 'slow'}},
            'type__': {'value': bond_type},
            'offloading': {'modes': {'value': {'mode_common': None}}}
        }
        attributes.update(iface_props)

        self.data.append({
            'name': bond_name,
            'type': NETWORK_INTERFACE_TYPES.bond,
            'attributes': attributes,
            'slaves': [
                {'name': self.other_nic['name']},
                {'name': self.empty_nic['name']}],
            'assigned_networks': self.other_nic['assigned_networks']
        })
        self.other_nic["assigned_networks"] = []

    def check_bond_creation(self, put_func, bond_name='bond0'):
        resp = put_func()
        self.assertEqual(resp.status_code, 200)

        resp = self.env.node_nics_get(self.env.nodes[0]["id"])
        self.assertEqual(resp.status_code, 200)

        bonds = filter(
            lambda iface: iface["type"] == NETWORK_INTERFACE_TYPES.bond,
            resp.json_body)
        self.assertEqual(len(bonds), 1)
        self.assertEqual(bonds[0]["name"], bond_name)
        modes = bonds[0]['attributes']['offloading']['modes']['value']
        self.assertDictEqual(
            modes, {'mode_common': None})

    def nics_bond_remove(self, put_func):
        resp = self.env.node_nics_get(self.env.nodes[0]["id"])
        self.assertEqual(resp.status_code, 200)
        self.data = resp.json_body
        for nic in self.data:
            if nic["type"] == NETWORK_INTERFACE_TYPES.bond:
                bond = nic
                break
        else:
            raise Exception("No bond was found unexpectedly")
        for nic in self.data:
            if nic["name"] == bond["slaves"][0]["name"]:
                nic["assigned_networks"] = bond["assigned_networks"]
                break
        else:
            raise Exception("NIC from bond wasn't found unexpectedly")
        self.data.remove(bond)

        resp = put_func()
        self.assertEqual(resp.status_code, 200)

    def test_nics_bond_delete(self):
        for put_func in (self.put_single, self.put_collection):
            self.get_node_nics_info()
            self.nics_bond_create_and_check(put_func)
            self.nics_bond_remove(put_func)

            resp = self.env.node_nics_get(self.env.nodes[0]["id"])
            self.assertEqual(resp.status_code, 200)

            for nic in resp.json_body:
                self.assertNotEqual(nic["type"], NETWORK_INTERFACE_TYPES.bond)

    def test_nics_linux_bond_create_delete(self):
        bond_name = 'bond0'
        for put_func in (self.put_single, self.put_collection):
            self.get_node_nics_info()
            self.prepare_bond_w_props(bond_name=bond_name)
            self.check_bond_creation(put_func, bond_name=bond_name)
            self.nics_bond_remove(put_func)

            resp = self.env.node_nics_get(self.env.nodes[0]["id"])
            self.assertEqual(resp.status_code, 200)

            for nic in resp.json_body:
                self.assertNotEqual(nic["type"], NETWORK_INTERFACE_TYPES.bond)

    def test_nics_ovs_bond_create_failed_without_dpdk(self):
        bond_name = 'bond0'
        self.prepare_bond_w_props(bond_name=bond_name,
                                  bond_type=BOND_TYPES.dpdkovs,
                                  bond_mode=BOND_MODES.balance_tcp)
        self.node_nics_put_check_error("Bond interface '{0}': DPDK should be"
                                       " enabled for 'dpdkovs' bond type".
                                       format(bond_name))

    @mock.patch.object(objects.NIC, 'dpdk_available')
    def test_nics_lnx_bond_create_failed_with_dpdk(self, m_dpdk_available):
        m_dpdk_available.return_value = True
        bond_name = 'bond0'
        self.prepare_bond_w_props(
            bond_name=bond_name,
            bond_type=BOND_TYPES.linux,
            iface_props={'dpdk': {'enabled': {'value': True}}})
        self.node_nics_put_check_error("Bond interface '{0}': DPDK can be"
                                       " enabled only for 'dpdkovs' bond type".
                                       format(bond_name))

    def test_nics_ovs_bond_update_failed_without_dpdk(self):
        bond_name = 'bond0'
        node = self.env.nodes[0]
        self.prepare_bond_w_props(bond_name=bond_name,
                                  bond_type=BOND_TYPES.linux)
        resp = self.put_single()
        self.assertEqual(resp.status_code, 200)

        self.data = self.env.node_nics_get(node.id).json_body
        bond = [iface for iface in self.data
                if iface['type'] == NETWORK_INTERFACE_TYPES.bond][0]
        bond['attributes']['type__']['value'] = BOND_TYPES.dpdkovs
        bond['attributes']['mode']['value']['value'] = BOND_MODES.balance_tcp
        self.node_nics_put_check_error(
            "Bond interface '{0}': DPDK should be enabled for 'dpdkovs' bond"
            " type".format(bond_name))

    @mock.patch.object(objects.Bond, 'dpdk_available')
    def test_nics_lnx_bond_update_failed_with_dpdk(self, m_dpdk_available):
        m_dpdk_available.return_value = True
        bond_name = 'bond0'
        node = self.env.nodes[0]
        self.prepare_bond_w_props(bond_name=bond_name,
                                  bond_type=BOND_TYPES.linux)
        resp = self.put_single()
        self.assertEqual(resp.status_code, 200)

        self.data = self.env.node_nics_get(node.id).json_body
        bond = [iface for iface in self.data
                if iface['type'] == NETWORK_INTERFACE_TYPES.bond][0]
        bond['attributes'] = {
            'type__': {'value': BOND_TYPES.linux},
            'dpdk': {'enabled': {'value': True}}}
        self.node_nics_put_check_error(
            "Bond interface '{0}': DPDK can be enabled only for 'dpdkovs' bond"
            " type".format(bond_name))

    def test_nics_bond_removed_on_node_unassign(self):
        self.get_node_nics_info()
        self.nics_bond_create_and_check(self.put_single)

        node = self.env.nodes[0]
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': self.cluster.id}
            ),
            jsonutils.dumps([{'id': node.id}]),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)

        self.assertIsNone(node.cluster)
        resp = self.env.node_nics_get(node.id)
        self.assertEqual(resp.status_code, 200)

        for nic in resp.json_body:
            self.assertNotEqual(nic["type"], NETWORK_INTERFACE_TYPES.bond)

    def test_nics_bond_removed_on_remove_node_from_cluster(self):
        self.get_node_nics_info()
        self.nics_bond_create_and_check(self.put_single)

        node = self.env.nodes[0]
        resp = self.app.put(
            reverse('ClusterHandler',
                    kwargs={'obj_id': self.cluster.id}),
            jsonutils.dumps({'nodes': []}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 200)

        self.assertIsNone(node.cluster)
        resp = self.env.node_nics_get(node.id)
        self.assertEqual(resp.status_code, 200)

        for nic in resp.json_body:
            self.assertNotEqual(nic["type"], NETWORK_INTERFACE_TYPES.bond)

    def test_nics_bond_create_failed_no_type(self):
        self.data.append({
            "name": 'ovs-bond0'
        })

        self.node_nics_put_check_error(
            "Node '{0}': each interface must have a "
            "type".format(self.env.nodes[0]["id"])
        )

    def test_nics_bond_create_failed_not_have_enough_data(self):
        self.data.append({
            "type": NETWORK_INTERFACE_TYPES.bond
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': each bond interface must have "
            "name".format(self.env.nodes[0]["id"])
        )

    def test_nics_bond_create_failed_unknown_mode(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": "unknown",
            "attributes": {
                'type__': {'value': BOND_TYPES.linux}
            },
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': bond interface 'ovs-bond0' has unknown mode "
            "'unknown'".format(self.env.nodes[0]["id"])
        )

    def test_nics_bond_create_failed_no_mode(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                'type__': {'value': BOND_TYPES.linux}
            },
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': bond interface 'ovs-bond0' doesn't have mode".format(
                self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_no_mode_in_properties(self):
        self.data.append({
            "name": 'bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                'xmit_hash_policy': {
                    'value': {'value': BOND_XMIT_HASH_POLICY.layer2_3}},
                'type__': {'value': BOND_TYPES.linux}
            },
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': bond interface 'bond0' doesn't have mode".format(
                self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_unknown_mode_in_properties(self):
        self.data.append({
            "name": 'bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                'type__': {'value': BOND_TYPES.linux},
                'mode': {'value': {'value': 'unknown'}}
            },
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': bond interface 'bond0' has unknown mode "
            "'unknown'".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_no_slaves(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": BOND_MODES.balance_slb,
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': each bond interface must have "
            "two or more slaves".format(self.env.nodes[0]["id"])
        )

    def test_nics_bond_create_failed_one_slave(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': each bond interface must have "
            "two or more slaves".format(self.env.nodes[0]["id"])
        )

    def test_nics_bond_create_failed_no_assigned_networks(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "type__": {'value': BOND_TYPES.ovs}
            },
            "mode": BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}', interface 'ovs-bond0': there is no "
            "'assigned_networks' list".format(self.env.nodes[0]["id"])
        )

    def test_nics_bond_create_failed_nic_is_used_twice(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "type__": {'value': BOND_TYPES.ovs}
            },
            "mode": BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.other_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': interface '{1}' is used in bonds more "
            "than once".format(self.env.nodes[0]["id"], self.other_nic["id"])
        )

    def test_nics_bond_create_failed_duplicated_assigned_networks(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": BOND_MODES.balance_slb,
            "attributes": {
                "type__": {'value': BOND_TYPES.ovs}
            },
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })

        self.node_nics_put_check_error(
            "Node '{0}': there is a duplicated network '{1}' in "
            "assigned networks (second occurrence is in interface "
            "'ovs-bond0')".format(
                self.env.nodes[0]["id"],
                self.other_nic["assigned_networks"][0]["id"])
        )

    def test_nics_bond_create_failed_unknown_interface(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": BOND_MODES.balance_slb,
            "attributes": {
                "type__": {'value': BOND_TYPES.ovs}
            },
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": "some_nic"}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': there is no interface 'some_nic' found for bond "
            "'ovs-bond0' in DB".format(self.env.nodes[0]["id"])
        )

    def test_nics_bond_create_failed_slave_has_assigned_networks(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "type__": {'value': BOND_TYPES.ovs}
            },
            "mode": BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
            "assigned_networks": []
        })

        self.node_nics_put_check_error(
            "Node '{0}': interface '{1}' cannot have assigned networks as it "
            "is used in bond".format(self.env.nodes[0]["id"],
                                     self.other_nic["id"])
        )

    def test_nics_bond_create_failed_slave_has_no_name(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "type__": {'value': BOND_TYPES.ovs}
            },
            "mode": BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"nic": self.empty_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}', interface 'ovs-bond0': each bond slave "
            "must have name".format(self.env.nodes[0]["id"])
        )

    @mock.patch.dict(settings.VERSION, {'feature_groups': []})
    def test_nics_bond_create_failed_admin_net_w_lacp_lnx(self):
        mode = BOND_MODES.l_802_3ad
        bond_nets = self.admin_nic["assigned_networks"] + \
            self.other_nic["assigned_networks"]
        self.data.append({
            "name": 'lnx-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "type__": {'value': BOND_TYPES.linux}
            },
            "mode": mode,
            "slaves": [
                {"name": self.admin_nic["name"]},
                {"name": self.other_nic["name"]}],
            "assigned_networks": bond_nets
        })

        self.admin_nic["assigned_networks"] = []
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': interface 'lnx-bond0' belongs to admin network "
            "and has lacp mode '{1}'".format(self.env.nodes[0]["id"], mode)
        )

    @mock.patch.dict(settings.VERSION, {'feature_groups': []})
    def test_nics_bond_create_failed_admin_net_w_lacp_ovs(self):
        mode = BOND_MODES.lacp_balance_tcp
        bond_nets = self.admin_nic["assigned_networks"] + \
            self.other_nic["assigned_networks"]
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "type__": {'value': BOND_TYPES.ovs}
            },
            "mode": mode,
            "slaves": [
                {"name": self.admin_nic["name"]},
                {"name": self.other_nic["name"]}],
            "assigned_networks": bond_nets
        })

        self.admin_nic["assigned_networks"] = []
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': interface 'ovs-bond0' belongs to admin network "
            "and has lacp mode '{1}'".format(self.env.nodes[0]["id"], mode)
        )

    def test_nics_bond_create_admin_net_w_lacp_experimental_mode(self):
        mode = BOND_MODES.lacp_balance_tcp
        bond_nets = self.admin_nic["assigned_networks"] + \
            self.other_nic["assigned_networks"]
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "type__": {'value': BOND_TYPES.ovs}
            },
            "mode": mode,
            "slaves": [
                {"name": self.admin_nic["name"]},
                {"name": self.other_nic["name"]}],
            "assigned_networks": bond_nets
        })

        self.admin_nic["assigned_networks"] = []
        self.other_nic["assigned_networks"] = []

        resp = self.put_single()
        self.assertEqual(resp.status_code, 200)

    def test_nics_bond_create_failed_admin_net_w_o_pxe_iface(self):
        mode = BOND_MODES.balance_slb
        bond_nets = [self.admin_nic["assigned_networks"][0]] + \
            self.other_nic["assigned_networks"]
        del self.admin_nic["assigned_networks"][0]
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "type__": {'value': BOND_TYPES.ovs}
            },
            "mode": mode,
            "slaves": [
                {"name": self.empty_nic["name"]},
                {"name": self.other_nic["name"]}],
            "assigned_networks": bond_nets
        })

        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': interface 'ovs-bond0' belongs to admin network "
            "and doesn't contain node's pxe interface 'eth0'".format(
                self.env.nodes[0]["id"])
        )

    def test_nics_bond_change_offloading_modes(self):
        self.get_node_nics_info()
        self.nics_bond_create_and_check(self.put_single)
        resp = self.app.get(
            reverse("NodeNICsHandler",
                    kwargs={"node_id": self.env.nodes[0]["id"]}),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        body = resp.json_body
        bonds = filter(
            lambda iface: iface["type"] == NETWORK_INTERFACE_TYPES.bond,
            body)
        self.assertEqual(1, len(bonds))

        bond_offloading_modes = bonds[0]['attributes'][
            'offloading']['modes']['value']
        self.assertEqual(len(bond_offloading_modes), 1)
        slaves = bonds[0]['slaves']

        self.assertEqual(2, len(slaves))
        self.assertIsNone(bond_offloading_modes['mode_common'])
        bond_offloading_modes['mode_common'] = True

        resp = self.env.node_nics_put(
            self.env.nodes[0]["id"],
            body)

        body = resp.json_body
        bonds = filter(
            lambda iface: iface["type"] == NETWORK_INTERFACE_TYPES.bond,
            body)
        self.assertEqual(1, len(bonds))

        bond_offloading_modes = bonds[0]['attributes'][
            'offloading']['modes']['value']
        self.assertEqual(len(bond_offloading_modes), 1)
        slaves = bonds[0]['slaves']

        self.assertEqual(2, len(slaves))
        self.assertTrue(bond_offloading_modes['mode_common'])

    def test_nics_bond_cannot_contain_sriov_enabled_interfaces(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "type__": {'value': BOND_TYPES.ovs}
            },
            "mode": BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.admin_nic["name"]},
                {"name": self.sriov_nic["name"]}],
            "assigned_networks": self.sriov_nic["assigned_networks"]
        })
        self.sriov_nic['attributes']['sriov']['enabled']['value'] = True
        self.sriov_nic['attributes']['sriov']['numvfs']['value'] = 2
        cluster_db = self.env.clusters[-1]
        cluster_attrs = objects.Cluster.get_editable_attributes(cluster_db)
        cluster_attrs['common']['libvirt_type']['value'] = HYPERVISORS.kvm
        objects.Cluster.update_attributes(
            cluster_db, {'editable': cluster_attrs})
        db().commit()

        self.node_nics_put_check_error(
            "Node '{0}': bond 'ovs-bond0' cannot contain SRIOV "
            "enabled interface '{1}'".format(self.env.nodes[0]["id"],
                                             self.sriov_nic['name'])
        )

    def test_nics_bond_create_failed_without_type__(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "mode": {'value': BOND_MODES.balance_slb}
            },
            "slaves": [
                {"name": self.admin_nic["name"]},
                {"name": self.sriov_nic["name"]}],
            "assigned_networks": self.sriov_nic["assigned_networks"]
        })
        self.node_nics_put_check_error(
            "Node '{0}', bond interface 'ovs-bond0': doesn't have "
            "attributes.type__".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_without_attributes(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.admin_nic["name"]},
                {"name": self.sriov_nic["name"]}],
            "assigned_networks": self.sriov_nic["assigned_networks"]
        })
        self.node_nics_put_check_error(
            "Node '{0}', bond interface 'ovs-bond0': doesn't have "
            "attributes".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_with_unexpected_type__(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "mode": {'value': {'value': BOND_MODES.balance_slb}},
                "type__": {'value': 'unexpected_type'},
            },
            "slaves": [
                {"name": self.admin_nic["name"]},
                {"name": self.sriov_nic["name"]}],
            "assigned_networks": self.sriov_nic["assigned_networks"]
        })
        self.node_nics_put_check_error(
            "Node '{0}', interface 'ovs-bond0': unknown type__ "
            "'unexpected_type'. type__ should be in '{1}'".format(
                self.env.nodes[0]["id"], ','.join([k for k in BOND_TYPES])))

    def test_each_bond_type_has_allowed_mode(self):
        for bond_type in BOND_TYPES:
            self.assertIsNotNone(
                network.NetAssignmentValidator.get_allowed_modes_for_bond_type(
                    bond_type)
            )

    def test_nics_bond_create_failed_with_incorrect_mode_for_type(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "attributes": {
                "mode": {'value': {'value': BOND_MODES.balance_rr}},
                "type__": {'value': BOND_TYPES.ovs},
            },
            "slaves": [
                {"name": self.admin_nic["name"]},
                {"name": self.sriov_nic["name"]}],
            "assigned_networks": self.sriov_nic["assigned_networks"]
        })
        allowed_modes = (BOND_MODES.active_backup,
                         BOND_MODES.balance_slb,
                         BOND_MODES.balance_tcp,
                         BOND_MODES.lacp_balance_tcp,
                         )
        self.node_nics_put_check_error(
            "Node '{0}', bond interface 'ovs-bond0': mode '{1}' is not "
            "allowed for type '{2}'. Allowed modes for '{2}' "
            "type: '{3}'".format(
                self.env.nodes[0]["id"], BOND_MODES.balance_rr, BOND_TYPES.ovs,
                allowed_modes))


class TestBondAttributesDefaultsHandler(BaseIntegrationTest):

    EXPECTED_ATTRIBUTES = {
        'type__': {
            'value': None,
            'type': 'hidden'
        },
        'mode': {
            'value': {
                'weight': 10,
                'type': 'select',
                'value': '',
                'label': 'Mode'
            },
            'metadata': {
                'weight': 10,
                'label': 'Mode'
            }
        },
        'offloading': {
            'metadata': {
                'weight': 20,
                'label': 'Offloading'
            },
            'disable': {
                'weight': 10,
                'type': 'checkbox',
                'value': False,
                'label': 'Disable Offloading'
            },
            'modes': {
                'weight': 20,
                'type': 'offloading_modes',
                'value': {},
                'label': 'Offloading Modes'
            }
        },
        'mtu': {
            'metadata': {
                'weight': 30,
                'label': 'MTU'
            },
            'value': {
                'weight': 10,
                'type': 'number',
                'nullable': True,
                'value': None,
                'label': 'Use Custom MTU',
                'min': 42,
                'max': 65536
            }
        },
        'dpdk': {
            'enabled': {
                'value': False,
                'label': 'Enable DPDK',
                'description': 'The Data Plane Development Kit (DPDK) '
                               'provides high-performance packet processing '
                               'libraries and user space drivers.',
                'type': 'checkbox',
                'weight': 10,
                'restrictions': [{
                    "settings:common.libvirt_type.value != 'kvm'":
                    "Only KVM hypervisor works with DPDK"
                }]
            },
            'metadata': {
                'label': 'DPDK',
                'weight': 40,
                'restrictions': [{
                    'condition':
                        "not ('experimental' in version:feature_groups)",
                    'action': "hide"
                }]
            }
        },
        'lacp': {
            'metadata': {
                'weight': 50,
                'label': 'Lacp'
            },
            'value': {
                'weight': 10,
                'type': 'select',
                'value': '',
                'label': 'Lacp'
            }
        },
        'lacp_rate': {
            'metadata': {
                'weight': 60,
                'label': 'Lacp rate'
            },
            'value': {
                'weight': 10,
                'type': 'select',
                'value': '',
                'label': 'Lacp rate'
            }
        },
        'xmit_hash_policy': {
            'metadata': {
                'weight': 70,
                'label': 'Xmit hash policy'
            },
            'value': {
                'weight': 10,
                'type': 'select',
                'value': '',
                'label': 'Xmit hash policy'
            }
        },
        'plugin_a_with_bond_attributes': {
            'metadata': {
                'label': 'Test base plugin',
                'class': 'plugin'
            },
            'plugin_name_text': {
                'value': 'value',
                'type': 'text',
                'description': 'Some description',
                'weight': 25,
                'label': 'label'
            }
        }
    }

    def setUp(self):
        super(TestBondAttributesDefaultsHandler, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={
                'name': uuid.uuid4().get_hex(),
                'version': 'newton-10.0',
                'operating_system': 'Ubuntu',
                'modes': [CLUSTER_MODES.ha_compact]},
            nodes_kwargs=[{'roles': ['controller']}])
        self.node = self.env.nodes[0]
        self.env.create_plugin(
            name='plugin_a_with_bond_attributes',
            package_version='5.0.0',
            cluster=self.cluster,
            bond_attributes_metadata=self.env.get_default_plugin_bond_config())

    def test_get_bond_default_attributes(self):
        resp = self.app.get(
            reverse(
                "NodeBondAttributesDefaultsHandler",
                kwargs={"node_id": self.node.id}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertDictEqual(self.EXPECTED_ATTRIBUTES, resp.json_body)
