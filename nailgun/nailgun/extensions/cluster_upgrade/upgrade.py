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
from nailgun import utils

from .objects import adapters


def merge_attributes(a, b):
    """Merge values of editable attributes.

    The values of the b attributes have precedence over the values
    of the a attributes.
    """
    attrs = copy.deepcopy(b)
    for section, pairs in six.iteritems(attrs):
        if section == "repo_setup" or section not in a:
            continue
        a_values = a[section]
        for key, values in six.iteritems(pairs):
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
        for key, value in six.iteritems(net):
            if (key not in ("cluster_id", "id", "meta", "group_id") and
                    key in source_net):
                net[key] = source_net[key]
    networking_params = new_settings["networking_parameters"]
    source_params = a["networking_parameters"]
    for key, value in six.iteritems(networking_params):
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
        return new_cluster

    @classmethod
    def create_cluster_clone(cls, orig_cluster, data):
        create_data = orig_cluster.get_create_data()
        create_data["name"] = data["name"]
        create_data["release_id"] = data["release_id"]
        new_cluster = adapters.NailgunClusterAdapter.create(create_data)
        return new_cluster

    @classmethod
    def copy_attributes(cls, orig_cluster, new_cluster):
        # TODO(akscram): Attributes should be copied including
        #                borderline cases when some parameters are
        #                renamed or moved into plugins. Also, we should
        #                to keep special steps in copying of parameters
        #                that know how to translate parameters from one
        #                version to another. A set of this kind of steps
        #                should define an upgrade path of a particular
        #                cluster.
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
            nets_serializer.serialize_for_cluster(orig_cluster.cluster),
            nets_serializer.serialize_for_cluster(new_cluster.cluster))

        orig_net_manager = orig_cluster.get_network_manager()
        new_net_manager = new_cluster.get_network_manager()

        new_net_manager.update(nets)
        vips = orig_net_manager.get_assigned_vips()
        for ng_name in vips:
            if ng_name not in (consts.NETWORKS.public,
                               consts.NETWORKS.management):
                vips.pop(ng_name)
        new_net_manager.assign_given_vips_for_net_groups(vips)
        new_net_manager.assign_vips_for_net_groups()
