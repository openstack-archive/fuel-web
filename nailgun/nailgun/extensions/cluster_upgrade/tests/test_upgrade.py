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
    def setUp(self):
        super(TestUpgradeHelperCloneCluster, self).setUp()

        self.serialize_nets = network_configuration. \
            NeutronNetworkConfigurationSerializer. \
            serialize_for_cluster

    def test_create_cluster_clone(self):
        new_cluster = self.helper.create_cluster_clone(self.cluster_61,
                                                       self.data)
        cluster_61_data = self.cluster_61.get_create_data()
        new_cluster_data = new_cluster.get_create_data()
        for key, value in cluster_61_data.items():
            if key in ("name", "release_id"):
                continue
            self.assertEqual(value, new_cluster_data[key])

    def test_copy_attributes(self):
        new_cluster = self.helper.create_cluster_clone(self.cluster_61,
                                                       self.data)
        self.assertNotEqual(self.cluster_61.generated_attrs,
                            new_cluster.generated_attrs)

        # Do some unordinary changes
        attrs = copy.deepcopy(self.cluster_61.editable_attrs)
        attrs["access"]["user"]["value"] = "operator"
        attrs["access"]["password"]["value"] = "secrete"
        self.cluster_61.editable_attrs = attrs

        self.helper.copy_attributes(self.cluster_61, new_cluster)

        self.assertEqual(self.cluster_61.generated_attrs,
                         new_cluster.generated_attrs)
        editable_attrs = self.cluster_61.editable_attrs
        for section, params in six.iteritems(new_cluster.editable_attrs):
            if section == "repo_setup":
                continue
            for key, value in six.iteritems(params):
                if key == "metadata":
                    continue
                self.assertEqual(editable_attrs[section][key]["value"],
                                 value["value"])

    def test_copy_network_config(self):
        new_cluster = self.helper.create_cluster_clone(self.cluster_61,
                                                       self.data)
        orig_net_manager = self.cluster_61.get_network_manager()
        serialize_nets = network_configuration.\
            NeutronNetworkConfigurationSerializer.\
            serialize_for_cluster

        # Do some unordinary changes
        nets = serialize_nets(self.cluster_61.cluster)
        nets["networks"][0].update({
            "cidr": "172.16.42.0/24",
            "gateway": "172.16.42.1",
            "ip_ranges": [["172.16.42.2", "172.16.42.126"]],
        })
        orig_net_manager.update(nets)
        orig_net_manager.assign_vips_for_net_groups()

        self.helper.copy_network_config(self.cluster_61, new_cluster)

        orig_nets = serialize_nets(self.cluster_61_db)
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
        orig_net_manager = self.cluster_61.get_network_manager()
        orig_net_manager.assign_vips_for_net_groups()
        new_cluster = self.helper.clone_cluster(self.cluster_61, self.data)
        relation = relations.UpgradeRelationObject.get_cluster_relation(
            self.cluster_61.id)
        self.assertEqual(relation.orig_cluster_id, self.cluster_61.id)
        self.assertEqual(relation.seed_cluster_id, new_cluster.id)

    def _check_different_attributes(self, orig_cluster, new_cluster):
        release = new_cluster.release.id
        nodegroups_id_maping = self.helper.get_nodegroups_id_mapping(
            orig_cluster, new_cluster
        )
        keys = ['release', 'id', 'group_id']
        orig_ngs = self.serialize_nets(orig_cluster.cluster)['networks']
        seed_ngs = self.serialize_nets(new_cluster.cluster)['networks']
        for orig_ng in orig_ngs:
            if (orig_ng['name'] == 'fuelweb_admin' and
                    not orig_ng.get('group_id')):
                continue
            for seed_ng in seed_ngs:
                if not seed_ng.get('group_id'):
                    continue
                if (orig_ng['name'] == seed_ng['name'] and
                        (nodegroups_id_maping[orig_ng['group_id']] == seed_ng[
                            'group_id'])):
                    self.assertEqual(seed_ng['group_id'],
                                     nodegroups_id_maping[orig_ng['group_id']])
                    if seed_ng.get('release'):
                        self.assertEqual(seed_ng['release'], release)
                    for key in keys:
                        orig_ng.pop(key, None)
                        seed_ng.pop(key, None)
                    break
        return orig_ngs, seed_ngs

    def _clone_cluster(self, template):
        new_cluster = self.helper.create_cluster_clone(self.cluster_61,
                                                       self.data)
        if template:
            net_template = self.env.read_fixtures(['network_template_80'])[0]
            new_cluster.network_template = net_template

        return new_cluster

    def sync_network_groups(self, template=None):
        new_cluster = self._clone_cluster(template)
        self.helper.sync_network_groups(self.cluster_61, new_cluster)
        orig_ngs, seed_ngs = self._check_different_attributes(self.cluster_61,
                                                              new_cluster)
        self.assertItemsEqual(orig_ngs, seed_ngs)

    def test_sync_network_groups(self):
        self.sync_network_groups()

    def test_sync_network_groups_with_template(self):
        self.sync_network_groups(template=True)

    def remove_network_groups(self):
        new_cluster = self._clone_cluster(None)
        self.helper.remove_network_groups(new_cluster)
        seed_ngs = self.serialize_nets(new_cluster.cluster)['networks']

        self.assertEqual(len(seed_ngs), 1)
        self.assertEqual(seed_ngs[0]['name'], 'fuelweb_admin')

    def test_remove_network_groups(self):
        self.remove_network_groups()

    def copy_network_groups(self, template=None):
        new_cluster = self._clone_cluster(template)
        nodegroups_id_maping = self.helper.get_nodegroups_id_mapping(
            self.cluster_61, new_cluster
        )
        release = new_cluster.release.id
        self.helper.remove_network_groups(new_cluster)
        self.helper.copy_network_groups(self.cluster_61, nodegroups_id_maping,
                                        release)
        orig_ngs, seed_ngs = self._check_different_attributes(self.cluster_61,
                                                              new_cluster)
        self.assertItemsEqual(orig_ngs, seed_ngs)

    def test_copy_network_groups(self):
        self.copy_network_groups()

    def test_copy_network_groups_with_template(self):
        self.copy_network_groups(template=True)
