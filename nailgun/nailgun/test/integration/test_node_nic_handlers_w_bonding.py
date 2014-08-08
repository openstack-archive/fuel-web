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

from nailgun.consts import NETWORK_INTERFACE_TYPES
from nailgun.consts import OVS_BOND_MODES
from nailgun.openstack.common import jsonutils
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
        self.data = jsonutils.loads(resp.body)
        self.admin_nic, self.other_nic, self.empty_nic = None, None, None
        for nic in self.data:
            net_names = [n["name"] for n in nic["assigned_networks"]]
            if "fuelweb_admin" in net_names:
                self.admin_nic = nic
            elif net_names:
                self.other_nic = nic
            else:
                self.empty_nic = nic
        self.assertTrue(self.admin_nic and self.other_nic and self.empty_nic)

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

    def nics_bond_create(self, put_func):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        resp = put_func()
        self.assertEqual(resp.status_code, 200)

        resp = self.env.node_nics_get(self.env.nodes[0]["id"])
        self.assertEqual(resp.status_code, 200)
        data = jsonutils.loads(resp.body)
        bonds = filter(
            lambda iface: iface["type"] == NETWORK_INTERFACE_TYPES.bond,
            data)
        self.assertEqual(len(bonds), 1)
        self.assertEqual(bonds[0]["name"], 'ovs-bond0')

    def nics_bond_remove(self, put_func):
        resp = self.env.node_nics_get(self.env.nodes[0]["id"])
        self.assertEqual(resp.status_code, 200)
        self.data = jsonutils.loads(resp.body)
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
            self.nics_bond_create(put_func)
            self.nics_bond_remove(put_func)

            resp = self.env.node_nics_get(self.env.nodes[0]["id"])
            self.assertEqual(resp.status_code, 200)
            data = jsonutils.loads(resp.body)
            for nic in data:
                self.assertNotEqual(nic["type"], NETWORK_INTERFACE_TYPES.bond)

    def test_nics_bond_removed_on_node_unassign(self):
        self.get_node_nics_info()
        self.nics_bond_create(self.put_single)

        node = self.env.nodes[0]
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': self.env.clusters[0]['id']}
            ),
            jsonutils.dumps([{'id': node.id}]),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)

        self.assertEqual(node.cluster, None)
        resp = self.env.node_nics_get(node.id)
        self.assertEqual(resp.status_code, 200)
        data = jsonutils.loads(resp.body)
        for nic in data:
            self.assertNotEqual(nic["type"], NETWORK_INTERFACE_TYPES.bond)

    def test_nics_bond_removed_on_remove_node_from_cluster(self):
        self.get_node_nics_info()
        self.nics_bond_create(self.put_single)

        node = self.env.nodes[0]
        resp = self.app.put(
            reverse('ClusterHandler',
                    kwargs={'obj_id': self.env.clusters[0]['id']}),
            jsonutils.dumps({'nodes': []}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(node.cluster, None)
        resp = self.env.node_nics_get(node.id)
        self.assertEqual(resp.status_code, 200)
        data = jsonutils.loads(resp.body)
        for nic in data:
            self.assertNotEqual(nic["type"], NETWORK_INTERFACE_TYPES.bond)

    def test_nics_bond_create_failed_no_type(self):
        self.data.append({
            "name": 'ovs-bond0'
        })

        self.node_nics_put_check_error(
            "Node '{0}': each interface must have a "
            "type".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_not_have_enough_data(self):
        self.data.append({
            "type": NETWORK_INTERFACE_TYPES.bond
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': each bond interface must have "
            "name".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_unknown_mode(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": "unknown",
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': bond interface 'ovs-bond0' has unknown mode "
            "'unknown'".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_no_mode(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': each bond interface must have "
            "mode".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_no_slaves(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': each bond interface must have "
            "two or more slaves".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_one_slave(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': each bond interface must have "
            "two or more slaves".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_no_assigned_networks(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}', interface 'ovs-bond0': there is no "
            "'assigned_networks' list".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_nic_is_used_twice(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.other_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': interface '{1}' is used in bonds more "
            "than once".format(self.env.nodes[0]["id"], self.other_nic["id"]))

    def test_nics_bond_create_failed_duplicated_assigned_networks(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
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
                self.other_nic["assigned_networks"][0]["id"]))

    def test_nics_bond_create_failed_unknown_interface(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": "some_nic"}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}': there is no interface 'some_nic' found for bond "
            "'ovs-bond0' in DB".format(self.env.nodes[0]["id"]))

    def test_nics_bond_create_failed_slave_has_assigned_networks(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"name": self.empty_nic["name"]}],
            "assigned_networks": []
        })

        self.node_nics_put_check_error(
            "Node '{0}': interface '{1}' cannot have assigned networks as it "
            "is used in bond".format(self.env.nodes[0]["id"],
                                     self.other_nic["id"]))

    def test_nics_bond_create_failed_slave_has_no_name(self):
        self.data.append({
            "name": 'ovs-bond0',
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {"name": self.other_nic["name"]},
                {"nic": self.empty_nic["name"]}],
            "assigned_networks": self.other_nic["assigned_networks"]
        })
        self.other_nic["assigned_networks"] = []

        self.node_nics_put_check_error(
            "Node '{0}', interface 'ovs-bond0': each bond slave "
            "must have name".format(self.env.nodes[0]["id"]))
