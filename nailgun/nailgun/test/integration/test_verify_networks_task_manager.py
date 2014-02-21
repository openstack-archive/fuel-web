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
from mock import patch

from nailgun.consts import NETWORK_INTERFACE_TYPES
from nailgun.consts import OVS_BOND_MODES
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


@patch('nailgun.rpc.receiver.NailgunReceiver._get_master_macs')
class TestVerifyNetworkTaskManagers(BaseIntegrationTest):

    def setUp(self):
        self.master_macs = [{'addr': 'bc:ae:c5:e0:f5:85'},
                            {'addr': 'ee:ae:c5:e0:f5:17'}]
        self.not_master_macs = [{'addr': 'ee:ae:ee:e0:f5:85'}]

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
    def test_network_verify_task_managers_dhcp_on_master(self, macs_mock):
        macs_mock.return_value = self.master_macs

        task = self.env.launch_verify_networks()
        self.env.wait_ready(task, 30)

    @fake_tasks()
    def test_network_verify_compares_received_with_cached(self, macs_mock):
        macs_mock.return_value = self.master_macs

        resp = self.app.get(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status)
        nets = json.loads(resp.body)

        nets['networks'][-1]["vlan_start"] = 500
        task = self.env.launch_verify_networks(nets)
        self.env.wait_ready(task, 30)

    @fake_tasks(fake_rpc=False)
    def test_network_verify_fails_if_admin_intersection(self,
                                                        mocked_rpc, macs_mock):
        macs_mock.return_value = self.master_macs

        resp = self.app.get(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status)
        nets = json.loads(resp.body)

        admin_ng = self.env.network_manager.get_admin_network_group()

        nets['networks'][-2]['cidr'] = admin_ng.cidr

        task = self.env.launch_verify_networks(nets)
        self.env.wait_error(task, 30)
        self.assertIn(
            "Address space intersection between networks:\n",
            task.message)
        self.assertIn("admin (PXE)", task.message)
        self.assertIn("fixed", task.message)
        self.assertEquals(mocked_rpc.called, False)

    @fake_tasks(fake_rpc=False)
    def test_network_verify_fails_if_untagged_intersection(self,
                                                           mocked_rpc,
                                                           macs_mock):
        macs_mock.return_value = self.master_macs

        resp = self.app.get(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status)
        nets = json.loads(resp.body)

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
        self.assertEquals(mocked_rpc.called, False)

    @fake_tasks()
    def test_verify_networks_less_than_2_nodes_error(self,
                                                     macs_mock):
        macs_mock.return_value = self.master_macs
        self.db.delete(self.env.nodes[0])
        self.db.commit()

        resp = self.app.get(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            headers=self.default_headers
        )
        nets = json.loads(resp.body)

        task = self.env.launch_verify_networks(nets)
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        error_msg = 'At least two nodes are required to be in ' \
                    'the environment for network verification.'
        self.assertEqual(task.message, error_msg)

    @fake_tasks()
    def test_network_verify_if_old_task_is_running(self,
                                                   macs_mock):
        macs_mock.return_value = self.master_macs

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
        self.assertEquals(400, resp.status)


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
        self.db.commit()

    @fake_tasks(fake_rpc=False)
    def test_network_verification_neutron_with_vlan_segmentation(
            self, mocked_rpc):
        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, 'error')
        self.assertEqual(
            u'Network verification on Neutron is not implemented yet',
            task.message
        )


class TestNetworkVerificationWithBonds(BaseIntegrationTest):

    def setUp(self):
        super(TestNetworkVerificationWithBonds, self).setUp()
        meta1 = self.env.default_metadata()
        meta2 = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta1, [
            {"name": "eth0", "mac": "00:00:00:00:00:66"},
            {"name": "eth1", "mac": "00:00:00:00:00:77"},
            {"name": "eth2", "mac": "00:00:00:00:00:88"}])
        self.env.set_interfaces_in_meta(meta2, [
            {"name": "eth0", "mac": "00:00:00:00:11:66"},
            {"name": "eth1", "mac": "00:00:00:00:22:77"},
            {"name": "eth2", "mac": "00:00:00:00:33:88"}])
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
            self.nics_bond_create(node, data, admin_nic, other_nic, empty_nic)
            self.verify_bonds(node)

    def verify_nics(self, node):
        resp = self.app.get(
            reverse('NodeNICsHandler',
                    kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEquals(resp.status, 200)
        data = json.loads(resp.body)
        admin_nic, other_nic, empty_nic = None, None, None
        for nic in data:
            net_names = [n['name'] for n in nic['assigned_networks']]
            if 'fuelweb_admin' in net_names:
                admin_nic = nic
            elif net_names:
                other_nic = nic
            else:
                empty_nic = nic
        self.assertTrue(admin_nic and other_nic and empty_nic)
        return data, admin_nic, other_nic, empty_nic

    def verify_bonds(self, node):
        resp = self.env.node_nics_get(node["id"])
        self.assertEqual(resp.status, 200)
        data = json.loads(resp.body)
        bond = filter(lambda nic: nic["type"] == NETWORK_INTERFACE_TYPES.bond,
                      data)
        self.assertEqual(len(bond), 1)
        self.assertEqual(bond[0]["name"], "ovs-bond0")

    def nics_bond_create(self, node, data, admin_nic, other_nic, empty_nic):
        data.append({
            "name": "ovs-bond0",
            "type": NETWORK_INTERFACE_TYPES.bond,
            "mode": OVS_BOND_MODES.balance_slb,
            "slaves": [
                {"name": other_nic["name"]},
                {"name": empty_nic["name"]},
            ],
            "assigned_networks": other_nic["assigned_networks"]
        })
        other_nic["assigned_networks"] = []
        resp = self.env.node_nics_put(node['id'], data)
        self.assertEqual(resp.status, 200)

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
        self.assertEquals(self.cluster.status, "stopped")
        verify_task = self.env.launch_verify_networks()
        self.env.wait_ready(verify_task, 60)

    @fake_tasks(fake_rpc=False)
    def test_network_verification_neutron_with_vlan_segmentation(
            self, mocked_rpc):
        # get Neutron L2 VLAN ID range
        l2params = self.env.clusters[0].neutron_config.L2
        vlan_rng_be = l2params["phys_nets"]["physnet2"]["vlan_range"]
        vlan_rng = set(range(vlan_rng_be[0], vlan_rng_be[1] + 1))

        # get nodes NICs for private network
        resp = self.app.get(reverse('NodeCollectionHandler'),
                            headers=self.default_headers)
        self.assertEquals(200, resp.status)
        priv_nics = {}
        for node in json.loads(resp.body):
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
