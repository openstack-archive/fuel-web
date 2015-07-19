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

import collections
import copy

from nailgun import consts
from nailgun import objects
from nailgun.objects.serializers import network_configuration
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import deployment_serializers
from nailgun import utils

from .objects.adapters import NailgunClusterAdapter
from .objects.adapters import NailgunNodeAdapter


def merge_attributes(a, b):
    attrs = copy.deepcopy(b)
    for section, pairs in attrs.iteritems():
        if section == "repo_setup" or section not in a:
            continue
        a_values = a[section]
        for key, values in pairs.iteritems():
            if key != "metadata" and key in a_values:
                values["value"] = a_values[key]["value"]
    return attrs


def merge_nets(a, b):
    new_settings = copy.deepcopy(b)
    source_networks = dict((n["name"], n) for n in a["networks"])
    for net in new_settings["networks"]:
        if net["name"] not in source_networks:
            continue
        source_net = source_networks[net["name"]]
        for key, value in net.iteritems():
            if (key not in ("cluster_id", "id", "meta", "group_id") and
                    key in source_net):
                net[key] = source_net[key]
    networking_params = new_settings["networking_parameters"]
    source_params = a["networking_parameters"]
    for key, value in networking_params.iteritems():
        if key not in source_params:
            continue
        networking_params[key] = source_params[key]
    return new_settings


class UpgradeHelper(object):
    network_serializers = {
        consts.CLUSTER_NET_PROVIDERS.neutron:
        network_configuration.NeutronNetworkConfigurationSerializer,
        consts.CLUSTER_NET_PROVIDERS.nova_network:
        network_configuration.NovaNetworkConfigurationSerializer,
    }

    @classmethod
    def clone_cluster(cls, orig_cluster, data):
        from .objects import relations

        new_cluster = cls.create_cluster_clone(orig_cluster, data)
        cls.copy_attributes(orig_cluster, new_cluster)
        cls.copy_network_config(orig_cluster, new_cluster)
        relations.UpgradeRelationObject.create_relation(orig_cluster.id,
                                                        new_cluster.id)

    @classmethod
    def create_cluster_clone(cls, orig_cluster, data):
        create_data = orig_cluster.get_create_data()
        create_data["name"] = data["name"]
        create_data["release_id"] = data["release_id"]
        new_cluster = NailgunClusterAdapter(
            objects.Cluster.create(create_data))
        return new_cluster

    @classmethod
    def copy_attributes(cls, orig_cluster, new_cluster):
        new_cluster.generated_attrs = utils.dict_merge(
            new_cluster.generated_attrs,
            orig_cluster.generated_attrs)
        new_cluster.editable_attrs = merge_attributes(
            orig_cluster.editable_attrs,
            new_cluster.editable_attrs)

    @classmethod
    def copy_network_config(cls, orig_cluster, new_cluster):
        nets_serializer = cls.network_serializers[orig_cluster.net_provider]
        nets = merge_nets(
            nets_serializer.serialize_for_cluster(orig_cluster),
            nets_serializer.serialize_for_cluster(new_cluster))

        orig_net_manager = orig_cluster.get_network_manager()
        new_net_manager = new_cluster.get_network_manager()

        new_net_manager.update(new_cluster, nets)
        vips = orig_net_manager.get_assigned_vips(orig_cluster)
        for ng_name in vips.keys():
            if ng_name not in set((consts.NETWORKS.public,
                                   consts.NETWORKS.management)):
                vips.pop(ng_name)
        new_net_manager.assign_given_vips_for_net_groups(new_cluster, vips)
        new_net_manager.assign_vips_for_net_groups(new_cluster)

    @classmethod
    def copy_controllers_ips_and_hostnames(cls,
                                           orig_cluster_id,
                                           seed_cluster_id):
        seed_cluster = NailgunClusterAdapter.get_by_uid(
            seed_cluster_id)
        orig_cluster = NailgunClusterAdapter.get_by_uid(
            orig_cluster_id)

        seed_controllers = NailgunClusterAdapter.get_nodes_by_role(
            seed_cluster, 'controller')
        orig_controllers = NailgunClusterAdapter.get_nodes_by_role(
            orig_cluster, 'controller')

        seed_manager = NailgunClusterAdapter(seed_cluster).\
            get_network_manager()
        orig_manager = NailgunClusterAdapter(orig_cluster).\
            get_network_manager()

        # Need to allocate ips for seed controllers
        cls.get_default_deployment_info(seed_cluster, seed_controllers)

        node_by_net_names = collections.defaultdict(list)
        nets_ips_by_node = collections.defaultdict(dict)

        # controller nodes will be mapped by set of network group names
        for orig_node in orig_controllers:
            orig_node_adapter = NailgunNodeAdapter(orig_node)
            ips_by_network_name = orig_manager.get_node_networks_ips(
                orig_node)
            ips_by_network_name.pop(consts.NETWORKS.fuelweb_admin, None)
            nets_ips_by_node[orig_node_adapter] = ips_by_network_name
            net_names = tuple(sorted(ips_by_network_name))
            node_by_net_names[net_names].append(orig_node_adapter)

        for seed_node in seed_controllers:
            seed_node_adapter = NailgunNodeAdapter(seed_node)
            ips_by_network_name = seed_manager.get_node_networks_ips(
                seed_node)
            ips_by_network_name.pop(consts.NETWORKS.fuelweb_admin, None)
            net_names = tuple(sorted(ips_by_network_name))
            orig_node_adapter = node_by_net_names[net_names].pop()

            seed_node_adapter.hostname = orig_node_adapter.hostname
            seed_manager.set_node_networks_ips(
                seed_node, nets_ips_by_node[orig_node_adapter])

    @staticmethod
    def get_default_deployment_info(cluster, nodes):
        # copied from DefaultDeploymentInfo

        graph = deployment_graph.AstuteGraph(cluster)
        deployment_serializers.serialize(graph, cluster, nodes,
                                         ignore_customized=True)
