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

import unittest2

from nailgun.consts import CLUSTER_STATUSES
from nailgun.consts import NETWORK_INTERFACE_TYPES
from nailgun.consts import OVS_BOND_MODES
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestVerifyNetworkTaskManagers(BaseIntegrationTest):

    def setUp(self):

        super(TestVerifyNetworkTaskManagers, self).setUp()

        meta1 = self.env.generate_interfaces_in_meta(2)
        mac1 = meta1['interfaces'][0]['mac']
        meta2 = self.env.generate_interfaces_in_meta(2)
        mac2 = meta2['interfaces'][0]['mac']
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": True, "meta": meta1, "mac": mac1},
                {"api": True, "meta": meta2, "mac": mac2},
            ]
        )

    def tearDown(self):
        self._wait_for_threads()
        super(TestVerifyNetworkTaskManagers, self).tearDown()

    @fake_tasks()
    def test_network_verify_task_managers_dhcp_on_master(self):
        task = self.env.launch_verify_networks()
        self.env.wait_ready(task, 30)

    @fake_tasks()
    def test_network_verify_compares_received_with_cached(self):

        resp = self.app.get(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        nets = resp.json_body

        nets['networks'][-1]["vlan_start"] = 500
        task = self.env.launch_verify_networks(nets)
        self.env.wait_ready(task, 30)

    @fake_tasks(fake_rpc=False)
    def test_network_verify_fails_if_admin_intersection(self, mocked_rpc):

        resp = self.app.get(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        nets = resp.json_body

        admin_ng = self.env.network_manager.get_admin_network_group()

        nets['networks'][-2]['cidr'] = admin_ng.cidr

        task = self.env.launch_verify_networks(nets)
        self.env.wait_error(task, 30)
        self.assertIn(
            "Address space intersection between networks:\n",
            task.message)
        self.assertIn("admin (PXE)", task.message)
        self.assertIn("fixed", task.message)
        self.assertEqual(mocked_rpc.called, False)

    @fake_tasks(fake_rpc=False)
    def test_network_verify_fails_if_untagged_intersection(self, mocked_rpc):

        resp = self.app.get(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        nets = resp.json_body

        for net in nets['networks']:
            if net['name'] in ('storage',):
                net['vlan_start'] = None

        task = self.env.launch_verify_networks(nets)
        self.env.wait_error(task, 30)
        self.assertIn(
            'Some untagged networks are assigned to the same physical '
            'interface. You should assign them to different physical '
            'interfaces. Affected:\n',
            task.message
        )
        for n in self.env.nodes:
            self.assertIn('"storage"', task.message)
        self.assertEqual(mocked_rpc.called, False)

    @fake_tasks()
    def test_verify_networks_less_than_2_nodes_error(self):
        self.db.delete(self.env.nodes[0])
        self.db.commit()

        resp = self.app.get(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        nets = resp.json_body

        task = self.env.launch_verify_networks(nets)
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        error_msg = 'At least two nodes are required to be in ' \
                    'the environment for network verification.'
        self.assertEqual(task.message, error_msg)

    @fake_tasks()
    def test_network_verify_when_env_not_ready(self):
        cluster_db = self.env.clusters[0]
        blocking_statuses = (
            CLUSTER_STATUSES.deployment,
            CLUSTER_STATUSES.update,
        )
        for status in blocking_statuses:
            cluster_db.status = status
            self.db.commit()

            resp = self.app.get(
                reverse(
                    'NovaNetworkConfigurationHandler',
                    kwargs={'cluster_id': self.env.clusters[0].id}
                ),
                headers=self.default_headers
            )
            nets = resp.json_body

            task = self.env.launch_verify_networks(nets)
            self.db.refresh(task)

            self.assertEqual(task.status, "error")
            error_msg = (
                "Environment is not ready to run network verification "
                "because it is in '{0}' state.".format(status)
            )
            self.assertEqual(task.message, error_msg)

    @fake_tasks()
    def test_network_verify_if_old_task_is_running(self):

        resp = self.app.get(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        nets = resp.body

        self.env.create_task(
            name="verify_networks",
            status="running",
            cluster_id=self.env.clusters[0].id
        )

        resp = self.app.put(
            reverse(
                'NovaNetworkConfigurationVerifyHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}),
            nets,
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    @unittest2.skip('Multicast is always disabled.')
    @fake_tasks(fake_rpc=False)
    def test_multicast_enabled_when_corosync_section_present(self, mocked_rpc):
        self.env.launch_verify_networks()
        self.assertIn('subtasks', mocked_rpc.call_args[0][1])
        subtasks = mocked_rpc.call_args[0][1]['subtasks']
        self.assertEqual(len(subtasks), 2)
        dhcp_subtask, multicast = subtasks[0], subtasks[1]
        self.assertEqual(dhcp_subtask['method'], 'check_dhcp')
        self.assertEqual(multicast['method'], 'multicast_verification')

    @unittest2.skip('Multicast is always disabled.')
    @fake_tasks(fake_rpc=False)
    def test_multicast_disabled_when_corosync_is_not_present(self, mocked_rpc):
        editable = copy.deepcopy(self.env.clusters[0].attributes.editable)
        del editable['corosync']
        self.env.clusters[0].attributes.editable = editable
        self.env.launch_verify_networks()
        self.assertIn('subtasks', mocked_rpc.call_args[0][1])
        subtasks = mocked_rpc.call_args[0][1]['subtasks']
        self.assertEqual(len(subtasks), 1)
        dhcp_subtask = subtasks[0]
        self.assertEqual(dhcp_subtask['method'], 'check_dhcp')


class TestVerifyNetworksDisabled(BaseIntegrationTest):

    def setUp(self):
        super(TestVerifyNetworksDisabled, self).setUp()
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [{
            "mac": "00:00:00:00:00:66",
            "max_speed": 1000,
            "name": "eth0",
            "current_speed": 1000
        }, {
            "mac": "00:00:00:00:00:77",
            "max_speed": 1000,
            "name": "eth1",
            "current_speed": None
        }, {
            "mac": "00:00:00:00:00:88",
            "max_speed": 1000,
            "name": "eth2",
            "current_speed": None}])
        self.env.create(
            cluster_kwargs={'status': 'operational',
                            'net_provider': 'neutron',
                            'net_segment_type': 'vlan'},
            nodes_kwargs=[
                {
                    'api': False,
                },
                {
                    'api': False,
                },
            ]
        )
        self.cluster = self.env.clusters[0]

    @fake_tasks()
    def test_network_verification_neutron_with_vlan_segmentation(self):
        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, 'running')
        self.env.wait_ready(task, 30)


class TestNetworkVerificationWithBonds(BaseIntegrationTest):

    def setUp(self):
        super(TestNetworkVerificationWithBonds, self).setUp()
        meta1 = self.env.default_metadata()
        meta2 = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta1, [
            {"name": "eth0", "mac": "00:00:00:00:00:66"},
            {"name": "eth1", "mac": "00:00:00:00:00:77"},
            {"name": "eth2", "mac": "00:00:00:00:00:88"}]
        )
        self.env.set_interfaces_in_meta(meta2, [
            {"name": "eth0", "mac": "00:00:00:00:11:66", "current_speed": 100},
            {"name": "eth1", "mac": "00:00:00:00:22:77", "current_speed": 100},
            {"name": "eth2", "mac": "00:00:00:00:33:88", "current_speed": 100}]
        )
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'gre'
            },
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True,
                 'meta': meta1},
                {'api': True,
                 'pending_addition': True,
                 'meta': meta2}
            ]
        )

        for node in self.env.nodes:
            data, admin_nic, other_nic, empty_nic = self.verify_nics(node)
            self.env.make_bond_via_api("ovs-bond0",
                                       OVS_BOND_MODES.balance_slb,
                                       [other_nic["name"], empty_nic["name"]],
                                       node["id"])
            self.verify_bonds(node)

    def verify_nics(self, node):
        resp = self.app.get(
            reverse('NodeNICsHandler',
                    kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        admin_nic, other_nic, empty_nic = None, None, None
        for nic in resp.json_body:
            net_names = [n['name'] for n in nic['assigned_networks']]
            if 'fuelweb_admin' in net_names:
                admin_nic = nic
            elif net_names:
                other_nic = nic
            else:
                empty_nic = nic
        self.assertTrue(admin_nic and other_nic and empty_nic)
        return resp.json_body, admin_nic, other_nic, empty_nic

    def verify_bonds(self, node):
        resp = self.env.node_nics_get(node["id"])
        self.assertEqual(resp.status_code, 200)

        bond = filter(lambda nic: nic["type"] == NETWORK_INTERFACE_TYPES.bond,
                      resp.json_body)
        self.assertEqual(len(bond), 1)
        self.assertEqual(bond[0]["name"], "ovs-bond0")

    @property
    def expected_args(self):
        expected_networks = [{u'vlans': [0, 101, 102], u'iface': u'eth0'},
                             {u'vlans': [0], u'iface': u'eth1'},
                             {u'vlans': [0], u'iface': u'eth2'}]
        _expected_args = []
        for node in self.env.nodes:
            _expected_args.append({u'uid': node['id'],
                                   u'networks': expected_networks})
        return _expected_args

    @fake_tasks()
    def test_network_verification_neutron_with_bonds(self):
        task = self.env.launch_verify_networks()
        self.assertEqual(task.cache['args']['nodes'], self.expected_args)
        self.env.wait_ready(task, 30)

    @fake_tasks()
    def test_network_verification_neutron_with_bonds_warn(self):
        resp = self.app.get(
            reverse(
                'NeutronNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        resp = self.app.put(
            reverse(
                'NeutronNetworkConfigurationVerifyHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}),
            resp.body,
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(202, resp.status_code)
        self.assertEqual(
            resp.json_body['result'],
            {u'warning': [u"Node '{0}': interface 'ovs-bond0' slave NICs have "
                          u"different or unrecognized speeds".format(
                              self.env.nodes[0].name)]})


class TestVerifyNeutronVlan(BaseIntegrationTest):

    def setUp(self):
        super(TestVerifyNeutronVlan, self).setUp()
        meta1 = self.env.default_metadata()
        meta2 = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta1, [
            {"name": "eth0", "mac": "00:00:00:00:00:66"},
            {"name": "eth1", "mac": "00:00:00:00:00:77"},
            {"name": "eth2", "mac": "00:00:00:00:00:88"}])
        self.env.set_interfaces_in_meta(meta2, [
            {"name": "eth0", "mac": "00:00:00:00:01:66"},
            {"name": "eth1", "mac": "00:00:00:00:01:77"},
            {"name": "eth2", "mac": "00:00:00:00:01:88"}])
        self.env.create(
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'vlan'
            },
            nodes_kwargs=[
                {
                    'api': True,
                    'pending_addition': True,
                    'meta': meta1
                },
                {
                    'api': True,
                    'pending_addition': True,
                    'meta': meta2
                }]
        )

    def tearDown(self):
        self._wait_for_threads()
        super(TestVerifyNeutronVlan, self).tearDown()

    @fake_tasks()
    def test_verify_networks_after_stop(self):
        self.cluster = self.env.clusters[0]
        self.env.launch_deployment()
        stop_task = self.env.stop_deployment()
        self.env.wait_ready(stop_task, 60)
        self.assertEqual(self.cluster.status, "stopped")
        verify_task = self.env.launch_verify_networks()
        self.env.wait_ready(verify_task, 60)

    @fake_tasks(fake_rpc=False)
    def test_network_verification_neutron_with_vlan_segmentation(
            self, mocked_rpc):
        # get Neutron L2 VLAN ID range
        vlan_rng_be = self.env.clusters[0].network_config.vlan_range
        vlan_rng = set(range(vlan_rng_be[0], vlan_rng_be[1] + 1))

        # get nodes NICs for private network
        resp = self.app.get(reverse('NodeCollectionHandler'),
                            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        priv_nics = {}
        for node in resp.json_body:
            for net in node['network_data']:
                if net['name'] == 'private':
                    priv_nics[node['id']] = net['dev']
                    break

        # check private VLAN range for nodes in Verify parameters
        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, 'running')
        for node in task.cache['args']['nodes']:
            for net in node['networks']:
                if net['iface'] == priv_nics[node['uid']]:
                    self.assertTrue(vlan_rng <= set(net['vlans']))
                    break
