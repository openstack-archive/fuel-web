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
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import objects
from nailgun.objects.serializers import network_configuration
from nailgun.orchestrator import deployment_graph
from nailgun.orchestrator import deployment_serializers
from nailgun import utils


def copy_vips(orig_cluster, new_cluster):
    orig_vips = {}
    for ng in orig_cluster.network_groups:
        vips = db.query(models.IPAddr).filter(
            models.IPAddr.network == ng.id,
            models.IPAddr.node.is_(None),
            models.IPAddr.vip_type.isnot(None),
        ).all()
        orig_vips[ng.name] = list(vips)

    new_vips = []
    for ng in new_cluster.network_groups:
        orig_ng_vips = orig_vips.get(ng.name)
        for vip in orig_ng_vips:
            ip_addr = models.IPAddr(
                network=ng.id,
                ip_addr=vip.ip_addr,
                vip_type=vip.vip_type,
            )
            new_vips.append(ip_addr)
    db.add_all(new_vips)
    db.flush()


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
#    upgrade_pathes = (
#    )
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
        relations.UpgradeRelationObject.create_relation(orig_cluster,
                                                        new_cluster)

    @classmethod
    def create_cluster_clone(cls, orig_cluster, data):
        create_data = orig_cluster.get_create_data()
        create_data["name"] = data["name"]
        create_data["release_id"] = data["release_id"]
        new_cluster = objects.Cluster.create(create_data)
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
        net_manager = cls.single.get_network_manager(instance=new_cluster)
        net_manager.update(new_cluster, nets)
        copy_vips(orig_cluster, new_cluster)
        net_manager.assign_vips_for_net_groups(new_cluster)

    @classmethod
    def clone_ips(cls, orig_cluster_id, seed_cluster_id):
        seed_cluster = objects.Cluster.get_by_uid(seed_cluster_id)
        orig_cluster = objects.Cluster.get_by_uid(orig_cluster_id)

        seed_controllers = objects.Cluster.get_nodes_by_role(seed_cluster,
                                                             'controller')
        orig_controllers = objects.Cluster.get_nodes_by_role(orig_cluster,
                                                             'controller')

        cls.assign_ips(seed_cluster, seed_controllers)

        node_by_net_names = collections.defaultdict(list)
        net_by_node = {}

        for node in orig_controllers:
            net_names = sorted(addr.network.name for addr in node.ip_addrs)
            net_by_node[node] = dict((addr.network.name, addr.ip_addr)
                                     for addr in node.ip_addrs)
            node_by_net_names[net_names].append(node)

        for node in seed_controllers:
            net_names = sorted(addr.network.name for addr in node.ip_addrs)
            orig_node = node_by_net_names[net_names].pop()
            for addr in node.ip_addrs:
                addr.ip_addr = net_by_node[orig_node][addr.network.name]

        db.flush()

    @staticmethod
    def assign_ips(cluster, nodes):
        # copied from DefaultDeploymentInfo
        graph = deployment_graph.AstuteGraph(cluster)
        deployment_serializers.serialize(graph, cluster, nodes,
                                         ignore_customized=True)
