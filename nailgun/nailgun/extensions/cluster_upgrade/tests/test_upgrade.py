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
from nailgun.objects.serializers import network_configuration

from . import base as base_tests
from ..objects import adapters
from ..objects import relations


class TestUpgradeHelperCloneCluster(base_tests.BaseCloneClusterTest):

    def setUp(self):
        super(TestUpgradeHelperCloneCluster, self).setUp()

        self.orig_net_manager = self.src_cluster.get_network_manager()

        self.serialize_nets = network_configuration.\
            NeutronNetworkConfigurationSerializer.\
            serialize_for_cluster

        self.public_net_data = {
            "cidr": "192.168.42.0/24",
            "gateway": "192.168.42.1",
            "ip_ranges": [["192.168.42.5", "192.168.42.11"]],
        }

    def test_create_cluster_clone(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        src_cluster_data = self.src_cluster.get_create_data()
        new_cluster_data = new_cluster.get_create_data()
        for key, value in src_cluster_data.items():
            if key in ("name", "release_id"):
                continue
            self.assertEqual(value, new_cluster_data[key])

    def test_copy_attributes(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        self.assertNotEqual(self.src_cluster.generated_attrs,
                            new_cluster.generated_attrs)

        # Do some unordinary changes
        attrs = copy.deepcopy(self.src_cluster.editable_attrs)
        attrs["access"]["user"]["value"] = "operator"
        attrs["access"]["password"]["value"] = "secrete"
        self.src_cluster.editable_attrs = attrs

        self.helper.copy_attributes(self.src_cluster, new_cluster)

        self.assertEqual(self.src_cluster.generated_attrs,
                         new_cluster.generated_attrs)
        editable_attrs = self.src_cluster.editable_attrs
        for section, params in six.iteritems(new_cluster.editable_attrs):
            if section == "repo_setup":
                continue
            for key, value in six.iteritems(params):
                if key == "metadata":
                    continue
                self.assertEqual(editable_attrs[section][key]["value"],
                                 value["value"])

    def update_public_net_params(self, networks):
        pub_net = self._get_pub_net(networks)
        pub_net.update(self.public_net_data)
        self.orig_net_manager.update(networks)

    def _get_pub_net(self, networks):
        return next(net for net in networks['networks'] if
                    net['name'] == consts.NETWORKS.public)

    def test_copy_network_config(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        # Do some unordinary changes to public network
        nets = self.serialize_nets(self.src_cluster.cluster)
        self.update_public_net_params(nets)

        self.helper.copy_network_config(self.src_cluster, new_cluster)

        new_nets = self.serialize_nets(new_cluster.cluster)

        public_net = self._get_pub_net(new_nets)

        self.assertEqual(public_net['cidr'], self.public_net_data['cidr'])
        self.assertEqual(public_net['gateway'],
                         self.public_net_data['gateway'])
        self.assertEqual(public_net['ip_ranges'],
                         self.public_net_data['ip_ranges'])

    def test_copy_vips(self):
        # save network information before node reassignment to seed cluster
        # as after that no VIP will be allocated/serialized due to
        # absence of assigned nodes for the source cluster
        orig_nets = self.serialize_nets(self.src_cluster.cluster)

        new_cluster = self.helper.clone_cluster(self.src_cluster, self.data)

        # we have to move node to new cluster before VIP assignment
        # because there is no point in the operation for a cluster
        # w/o nodes
        node = adapters.NailgunNodeAdapter(self.src_cluster.cluster.nodes[0])
        self.helper.assign_node_to_cluster(node, new_cluster, node.roles, [])

        self.helper.copy_vips(self.src_cluster, new_cluster)

        new_nets = self.serialize_nets(new_cluster.cluster)

        self.assertEqual(orig_nets["management_vip"],
                         new_nets["management_vip"])
        self.assertEqual(orig_nets["management_vrouter_vip"],
                         new_nets["management_vrouter_vip"])
        self.assertEqual(orig_nets["public_vip"],
                         new_nets["public_vip"])
        self.assertEqual(orig_nets["public_vrouter_vip"],
                         new_nets["public_vrouter_vip"])

    def test_clone_cluster(self):
        self.orig_net_manager.assign_vips_for_net_groups()
        new_cluster = self.helper.clone_cluster(self.src_cluster, self.data)
        relation = relations.UpgradeRelationObject.get_cluster_relation(
            self.src_cluster.id)
        self.assertEqual(relation.orig_cluster_id, self.src_cluster.id)
        self.assertEqual(relation.seed_cluster_id, new_cluster.id)
