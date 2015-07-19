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

import copy
import six

from nailgun import consts
from nailgun import objects
from nailgun.objects.serializers import network_configuration
from nailgun.test import base

from . import base as base_tests
from .. import upgrade
from ..objects import relations


class TestUpgradeHelperCloneCluster(base_tests.BaseCloneClusterTest):
    def test_create_cluster_clone(self):
        new_cluster = self.helper.create_cluster_clone(self.orig_cluster,
                                                       self.data)
        orig_cluster_data = self.orig_cluster.get_create_data()
        new_cluster_data = new_cluster.get_create_data()
        for key, value in orig_cluster_data.items():
            if key in ("name", "release_id"):
                continue
            self.assertEqual(value, new_cluster_data[key])

    def test_copy_attributes(self):
        new_cluster = self.helper.create_cluster_clone(self.orig_cluster,
                                                       self.data)
        self.assertNotEqual(self.orig_cluster.generated_attrs,
                            new_cluster.generated_attrs)

        # Do some unordinary changes
        attrs = copy.deepcopy(self.orig_cluster.editable_attrs)
        attrs["access"]["user"]["value"] = "operator"
        attrs["access"]["password"]["value"] = "secrete"
        self.orig_cluster.editable_attrs = attrs

        self.helper.copy_attributes(self.orig_cluster, new_cluster)

        self.assertEqual(self.orig_cluster.generated_attrs,
                         new_cluster.generated_attrs)
        editable_attrs = self.orig_cluster.editable_attrs
        for section, params in six.iteritems(new_cluster.editable_attrs):
            if section == "repo_setup":
                continue
            for key, value in six.iteritems(params):
                if key == "metadata":
                    continue
                self.assertEqual(editable_attrs[section][key]["value"],
                                 value["value"])

    def test_copy_network_config(self):
        new_cluster = self.helper.create_cluster_clone(self.orig_cluster,
                                                       self.data)
        orig_net_manager = self.orig_cluster.get_network_manager()
        new_net_manager = new_cluster.get_network_manager()

        # Do some unordinary changes
        nets = network_configuration.NeutronNetworkConfigurationSerializer.\
            serialize_for_cluster(self.orig_cluster.cluster)
        nets["networks"][0].update({
            "cidr": "172.16.42.0/24",
            "gateway": "172.16.42.1",
            "ip_ranges": [["172.16.42.2", "172.16.42.126"]],
        })
        orig_net_manager.update(nets)
        orig_net_manager.assign_vips_for_net_groups()

        self.helper.copy_network_config(self.orig_cluster, new_cluster)

        orig_vips = orig_net_manager.get_assigned_vips()
        new_vips = new_net_manager.get_assigned_vips()
        for net_name in (consts.NETWORKS.public,
                         consts.NETWORKS.management):
            for vip_type in consts.NETWORK_VIP_TYPES:
                self.assertEqual(orig_vips[net_name][vip_type],
                                 new_vips[net_name][vip_type])

    def test_clone_cluster(self):
        orig_net_manager = self.orig_cluster.get_network_manager()
        orig_net_manager.assign_vips_for_net_groups()
        new_cluster = self.helper.clone_cluster(self.orig_cluster, self.data)
        relation = relations.UpgradeRelationObject.get_cluster_relation(
            self.orig_cluster.id)
        self.assertEqual(relation.orig_cluster_id, self.orig_cluster.id)
        self.assertEqual(relation.seed_cluster_id, new_cluster.id)


class TestUpgradeHelperCloneIPs(base.BaseIntegrationTest):
    helper = upgrade.UpgradeHelper

    def test_copy_ips_and_hostnames(self):
        orig_cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}] * 2)
        seed_cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'role': 'controller'}] * 2)
        self.helper.get_default_deployment_info(orig_cluster, '')

        self.helper.copy_controllers_ips_and_hostnames(
            orig_cluster.id, seed_cluster.id)

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
