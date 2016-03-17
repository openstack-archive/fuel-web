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

from nailgun.objects.serializers import network_configuration

from . import base as base_tests
from ..objects import relations


class TestUpgradeHelperCloneCluster(base_tests.BaseCloneClusterTest):
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

    def test_copy_network_config(self):
        new_cluster = self.helper.create_cluster_clone(self.src_cluster,
                                                       self.data)
        orig_net_manager = self.src_cluster.get_network_manager()
        serialize_nets = network_configuration.\
            NeutronNetworkConfigurationSerializer.\
            serialize_for_cluster

        # Do some unordinary changes
        nets = serialize_nets(self.src_cluster.cluster)
        nets["networks"][0].update({
            "cidr": "172.16.42.0/24",
            "gateway": "172.16.42.1",
            "ip_ranges": [["172.16.42.2", "172.16.42.126"]],
        })
        orig_net_manager.update(nets)
        orig_net_manager.assign_vips_for_net_groups()

        self.helper.copy_network_config(self.src_cluster, new_cluster)

        orig_nets = serialize_nets(self.src_cluster_db)
        new_nets = serialize_nets(new_cluster.cluster)
        self.assertEqual(orig_nets["management_vip"],
                         new_nets["management_vip"])
        self.assertEqual(orig_nets["management_vrouter_vip"],
                         new_nets["management_vrouter_vip"])
        self.assertEqual(orig_nets["public_vip"],
                         new_nets["public_vip"])
        self.assertEqual(orig_nets["public_vrouter_vip"],
                         new_nets["public_vrouter_vip"])

    def test_clone_cluster(self):
        orig_net_manager = self.src_cluster.get_network_manager()
        orig_net_manager.assign_vips_for_net_groups()
        new_cluster = self.helper.clone_cluster(self.src_cluster, self.data)
        relation = relations.UpgradeRelationObject.get_cluster_relation(
            self.src_cluster.id)
        self.assertEqual(relation.orig_cluster_id, self.src_cluster.id)
        self.assertEqual(relation.seed_cluster_id, new_cluster.id)
