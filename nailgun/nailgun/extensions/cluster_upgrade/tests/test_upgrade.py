# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

from nailgun import objects
from nailgun.test.base import BaseIntegrationTest

from ..upgrade import UpgradeHelper


class TestUpgradeHelper(BaseIntegrationTest):

    def test_copy_ips_and_hostnames(self):
        orig_cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}] * 2)
        seed_cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}] * 2)
        UpgradeHelper.get_default_deployment_info(orig_cluster, '')

        UpgradeHelper.copy_ips_and_hostnames(orig_cluster.id, seed_cluster.id)

        orig_manager = objects.Cluster.get_network_manager(
            instance=orig_cluster)
        seed_manager = objects.Cluster.get_network_manager(
            instance=seed_cluster)

        for orig_node in orig_cluster.nodes:
            seed_node = objects.Node.get_by_hostname(
                orig_node.hostname, seed_cluster.id)
            orig_ips_by_net_names = orig_manager.get_node_networks_ips(
                orig_node)
            seed_ips_by_net_names = seed_manager.get_node_networks_ips(
                seed_node)
            self.assertEquals(orig_ips_by_net_names, seed_ips_by_net_names)
