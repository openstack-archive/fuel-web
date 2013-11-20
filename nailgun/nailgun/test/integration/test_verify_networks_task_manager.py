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
            task.message,
            "Address space intersection between networks: "
            "admin (PXE), fixed."
        )
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
            self.assertIn(
                '"floating", "storage", "public" networks '
                'at node "{0}"'.format(n.name),
                task.message
            )
        self.assertEquals(mocked_rpc.called, False)

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
            cluster_kwargs={
                'net_provider': 'neutron',
                'net_segment_type': 'vlan'
            },
            nodes_kwargs=[
                {
                    'api': True,
                    'roles': ['controller'],
                    'pending_addition': True,
                    'meta': meta,
                    'mac': "00:00:00:00:00:66"
                },
            ]
        )
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
        self.cluster.status = 'operational'
        self.db.commit()

    @fake_tasks(fake_rpc=False)
    def test_network_verification_neutron_with_vlan_segmentation(
            self, mocked_rpc):
        task = self.env.launch_verify_networks()
        self.assertEqual(task.status, 'error')
        self.assertEqual(
            (u'Network verification on Neutron is not implemented yet'),
            task.message
        )
