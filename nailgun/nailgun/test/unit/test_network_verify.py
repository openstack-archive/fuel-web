# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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
from nailgun import objects
from nailgun.task.task import VerifyNetworksTask
from nailgun.test.base import BaseTestCase


class TestNetworkVerification(BaseTestCase):

    def setUp(self):
        super(TestNetworkVerification, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={
                "api": False,
                "net_provider": consts.CLUSTER_NET_PROVIDERS.neutron
            },
            nodes_kwargs=[
                {"api": False,
                 "pending_addition": True},
            ]
        )

    def test_verify_networks_skips_dpdk_interface(self):
        node = self.env.nodes[0]
        node_json = {
            'uid': node.id,
            'name': node.name,
            'status': node.status,
            'networks': [],
            'excluded_networks': [],
        }
        dpdk_iface = None
        network_config = []
        for iface in node.interfaces:
            for ng in iface.assigned_networks_list:
                vlans = []
                if ng.name == consts.NETWORKS.private:
                    vlans = [1234, 1235]
                    dpdk_iface = iface
                network_config.append({'name': ng.name, 'vlans': vlans})

        dpdk_iface.interface_properties['dpdk']['enabled'] = True

        task = VerifyNetworksTask(None, network_config)
        task.get_ifaces_on_deployed_node(node, node_json, [])

        # DPDK-enabled interface should be skipped in network verification
        self.assertNotIn({'iface': dpdk_iface.name, 'vlans': [0]},
                         node_json['networks'])
        # Private vlans should be skipped for DPDK-enabled interface
        self.assertNotIn({'iface': dpdk_iface.name, 'vlans': [1234, 1235]},
                         node_json['networks'])

    def test_skip_private_net_for_the_only_node_wo_dpdk(self):
        self.env.create_node(cluster_id=self.cluster.id,
                             pending_addition=True,
                             roles=['compute'])
        self.assertEqual(len(self.env.nodes), 2)

        dpdk_iface = None
        network_config = []
        private_ifaces = {}
        for node in self.env.nodes:
            nic_1 = node.interfaces[0]
            nic_2 = node.interfaces[1]
            default_vlans = {
                consts.NETWORKS.public: [100],
                consts.NETWORKS.storage: [101],
                consts.NETWORKS.management: [102],
                consts.NETWORKS.fuelweb_admin: [103],
                consts.NETWORKS.private: [1234, 1235]
            }

            if not dpdk_iface:
                dpdk_iface = nic_2
            nets_1 = nic_1.assigned_networks_list
            nets_2 = nic_2.assigned_networks_list

            for i, net in enumerate(nets_1):
                if net['name'] == consts.NETWORKS.private:
                    nets_2.append(nets_1.pop(i))
                    break
            objects.NIC.assign_networks(nic_1, nets_1)
            objects.NIC.assign_networks(nic_2, nets_2)

            node.status = consts.NODE_STATUSES.ready
            for iface in node.interfaces:
                for ng in iface.assigned_networks_list:
                    network_config.append({'name': ng.name,
                                           'vlans': default_vlans[ng.name]})
                    if ng.name == consts.NETWORKS.private:
                        private_ifaces[node.name] = iface.name

        dpdk_iface.interface_properties['dpdk']['enabled'] = True

        task = models.Task(
            name=consts.TASK_NAMES.check_networks,
            cluster=self.cluster
        )

        verify_task = VerifyNetworksTask(task, network_config)

        message = verify_task.get_message_body()
        for node in message['nodes']:
            self.assertNotIn(private_ifaces[node['name']],
                             (n['iface'] for n in node['networks']))

    def test_verify_networks_checks_dpdk_interface(self):
        node = self.env.nodes[0]
        node_json = {
            'uid': node.id,
            'name': node.name,
            'status': node.status,
            'networks': [],
            'excluded_networks': [],
        }
        dpdk_iface = None
        private_iface = None
        private_ng = None
        network_config = []
        for iface in node.interfaces:
            for ng in iface.assigned_networks_list:
                vlans = []
                if ng.name == consts.NETWORKS.public:
                    dpdk_iface = iface
                elif ng.name == consts.NETWORKS.private:
                    private_iface = iface
                    private_ng = ng
                    vlans = [1236, 1237]
                else:
                    continue
                network_config.append({'name': ng.name, 'vlans': vlans})

        dpdk_iface.interface_properties['dpdk'].update({'available': True,
                                                        'enabled': True})
        private_iface.assigned_networks_list = [private_ng]

        task = VerifyNetworksTask(None, network_config)
        task.get_ifaces_on_deployed_node(node, node_json, [])

        # DPDK-enabled interface should not be skipped in network verification
        # because Private network is not assigned to it
        self.assertIn({'iface': dpdk_iface.name, 'vlans': [0]},
                      node_json['networks'])
        # Private vlans should not be skipped in network verification
        self.assertIn({'iface': private_iface.name, 'vlans': [1236, 1237]},
                      node_json['networks'])
