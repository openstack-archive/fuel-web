#    Copyright 2014 Mirantis, Inc.
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

from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun.network import connectivity
from nailgun import objects
from nailgun.test import base


class TestConnectivityCheck(base.BaseTestCase):

    def setUp(self):
        super(TestConnectivityCheck, self).setUp()
        self.env.create(
            nodes_kwargs=[{'api': False}, {'api': False}])
        self.node1 = self.env.nodes[0]
        self.node2 = self.env.nodes[1]
        self.task = objects.Task.create({'name': 'verify_networks'})
        self.task_cache = {
            "args":
            {
                "task_uuid": self.task.uuid,
                "nodes": [
                    {"uid": self.node1.uid,
                     "networks": [{"vlans": [0, 101, 102], "iface": "eth0"},
                                  {"vlans": [0], "iface": "eth1"}]},
                    {"uid": self.node2.uid,
                     "networks": [{"vlans": [0, 101, 102], "iface": "eth0"},
                                  {"vlans": [0], "iface": "eth1"}]}]
            }
        }
        objects.Task.update(self.task, {'cache': self.task_cache})

    def test_successfull_connectivity_task(self):
        expected_response = {
            "status": "ready",
            "progress": 100,
            "task_uuid": self.task.uuid,
            "nodes": [
                {"uid": self.node1.uid,
                 "networks": [{"vlans": [0], "iface": "eth1"},
                              {"vlans": [0, 101, 102], "iface": "eth0"}]},
                {"uid": self.node2.uid,
                 "networks": [{"vlans": [0], "iface": "eth1"},
                              {"vlans": [0, 101, 102], "iface": "eth0"}]}]}

        check = connectivity.Check(expected_response)
        check.run()
        self.assertEqual(self.task.status, 'ready')

    def test_failure_wo_bonds(self):
        """Test verifies if some packets received on another interface -
        connectivity verification will fail if no bond configured
        """
        expected_response = {
            "status": "ready",
            "progress": 100,
            "task_uuid": self.task.uuid,
            "nodes": [
                {"uid": self.node1.uid,
                 "networks": [{"vlans": [0, 101, 102], "iface": "eth1"},
                              {"vlans": [], "iface": "eth0"}]},
                {"uid": self.node2.uid,
                 "networks": [{"vlans": [0], "iface": "eth1"},
                              {"vlans": [0, 101, 102], "iface": "eth0"}]}]}
        check = connectivity.Check(expected_response)
        check.run()
        self.assertEqual(self.task.status, 'error')

    def test_failure_with_lacp_bond(self):
        """Test verifies that if lacp bond is configured then atleast one
        response is enough to verify network connectivity
        """
        expected_response = {
            "status": "ready",
            "progress": 100,
            "task_uuid": self.task.uuid,
            "nodes": [
                {"uid": self.node1.uid,
                 "networks": [{"vlans": [0, 101, 102], "iface": "eth1"},
                              {"vlans": [], "iface": "eth0"}]},
                {"uid": self.node2.uid,
                 "networks": [{"vlans": [0], "iface": "eth1"},
                              {"vlans": [0, 101, 102], "iface": "eth0"}]}]}

        for node in self.env.nodes:
            bond = models.NodeBondInterface(
                name='ovs-test0',
                node=node,
                slaves=node.nic_interfaces,
                mode=consts.OVS_BOND_MODES.lacp_balance_tcp)
            self.db.add(bond)
        self.db.flush()
        check = connectivity.Check(expected_response)
        check.run()
        self.assertEqual(self.task.status, 'ready')
