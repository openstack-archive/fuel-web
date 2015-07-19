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
        cluster0 = self.env.create(cluster_kwargs={'api': False,
                                                   'name': 'cluster0'},
                                   nodes_kwargs=[{'role': 'controller'}] * 2)
        cluster1 = self.env.create(cluster_kwargs={'api': False,
                                                   'name': 'cluster1'},
                                   nodes_kwargs=[{'role': 'conroller'}] * 2)
        UpgradeHelper.get_default_deployment_info(cluster0, '')

        UpgradeHelper.copy_ips_and_hostnames(cluster0.id, cluster1.id)
        manager0 = objects.Cluster.get_network_manager(instance=cluster0)
        manager1 = objects.Cluster.get_network_manager(instance=cluster1)

        for orig_node in cluster0.nodes:
            seed_node = objects.Node.get_by_hostname(
                orig_node.hostname, cluster1.id)
            ip_by_net_names0 = manager0.node_ip_by_network_name(orig_node)
            ip_by_net_names1 = manager1.node_ip_by_network_name(seed_node)
            self.assertEquals(ip_by_net_names0, ip_by_net_names1)
