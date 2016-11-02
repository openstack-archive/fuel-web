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
from distutils import version
import six

from nailgun import consts
from nailgun.db import db
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
        cls.sync_network_groups(orig_cluster, new_cluster)
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
    def sync_network_groups(cls, orig_cluster, new_cluster):
        cls.remove_network_groups(new_cluster)
        nodegroups_id_maping = cls.get_nodegroups_id_mapping(orig_cluster,
                                                             new_cluster)
        release = new_cluster.release.id
        cls.copy_network_groups(orig_cluster, nodegroups_id_maping, release)

    @classmethod
    def remove_network_groups(cls, cluster):
        seed_ng = cluster.get_network_groups()
        for ng in seed_ng:
            if cls.is_default_admin_network(ng):
                continue
            adapters.NailgunNetworkGroupAdapter.delete(ng.network_group)
        db().commit()

    @staticmethod
    def is_default_admin_network(ng):
        return ng.name == 'fuelweb_admin' and not ng.nodegroup

    @classmethod
    def copy_network_groups(cls, orig_cluster, nodegroups_id_maping, release):
        nets_serializer = cls.network_serializers[orig_cluster.net_provider]
        orig_net = nets_serializer.serialize_for_cluster(orig_cluster.cluster)
        data_to_update = {}
        for ng in orig_net['networks']:
            if (cls.is_default_admin_network(
                    adapters.NailgunNetworkGroupAdapter.get_by_uid(ng['id']))):
                continue
            data_to_update['ip_ranges'] = ng['ip_ranges']
            if ng['meta']['notation'] == 'ip_ranges':
                ng['meta']['ip_range'] = ng['ip_ranges'][0]
            data = {
                'name': ng['name'],
                'release': release,
                'vlan_start': ng['vlan_start'],
                'cidr': ng['cidr'],
                'gateway': ng['gateway'],
                'group_id': nodegroups_id_maping[ng['group_id']],
                'meta': ng['meta']
            }
            net_group = adapters.NailgunNetworkGroupAdapter.create(data)
            adapters.NailgunNetworkGroupAdapter.update(net_group,
                                                       data_to_update)
        db().commit()

    @classmethod
    def transform_vips_for_net_groups_70(cls, vips):
        """Rename or remove types of VIPs for 7.0 network groups.

        This method renames types of VIPs from older releases (<7.0) to
        be compatible with network groups of the 7.0 release according
        to the rules:

            management: haproxy -> management
            public: haproxy -> public
            public: vrouter -> vrouter_pub

        Note, that in the result VIPs are present only those IPs that
        correspond to the given rules.
        """
        rename_vip_rules = {
            "management": {
                "haproxy": "management",
                "vrouter": "vrouter",
            },
            "public": {
                "haproxy": "public",
                "vrouter": "vrouter_pub",
            },
        }
        renamed_vips = collections.defaultdict(dict)
        for ng_name, vips in six.iteritems(vips):
            ng_vip_rules = rename_vip_rules[ng_name]
            for vip_type, vip_addr in six.iteritems(vips):
                if vip_type not in ng_vip_rules:
                    continue
                new_vip_type = ng_vip_rules[vip_type]
                renamed_vips[ng_name][new_vip_type] = vip_addr
        return renamed_vips

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
        # NOTE(akscram): In the 7.0 release was introduced networking
        #                templates that use the vip_type column as
        #                unique names of VIPs.
        if version.LooseVersion(orig_cluster.release.environment_version) < \
                version.LooseVersion("7.0"):
            vips = cls.transform_vips_for_net_groups_70(vips)
        new_net_manager.assign_given_vips_for_net_groups(vips)
        new_net_manager.assign_vips_for_net_groups()

    @classmethod
    def assign_node_to_cluster(cls, node, seed_cluster):
        orig_cluster = adapters.NailgunClusterAdapter.get_by_uid(
            node.cluster_id)

        orig_manager = orig_cluster.get_network_manager()
        seed_manager = seed_cluster.get_network_manager()

        netgroups_id_mapping = cls.get_netgroups_id_mapping(
            orig_cluster, seed_cluster)

        node.update_cluster_assignment(seed_cluster)
        seed_manager.set_node_netgroups_ids(node, netgroups_id_mapping)
        if not seed_cluster.network_template:
            orig_manager.set_nic_assignment_netgroups_ids(
                node, netgroups_id_mapping)
            orig_manager.set_bond_assignment_netgroups_ids(
                node, netgroups_id_mapping)
        node.add_pending_change(consts.CLUSTER_CHANGES.interfaces)

    @classmethod
    def get_netgroups_id_mapping(self, orig_cluster, seed_cluster):
        orig_ng = orig_cluster.get_network_groups()
        seed_ng = seed_cluster.get_network_groups()

        seed_ng_dict = {(ng.name, ng.nodegroup.name): ng.id for ng in seed_ng}
        mapping = {ng.id: seed_ng_dict[(ng.name, ng.nodegroup.name)]
                   for ng in orig_ng}
        mapping[orig_cluster.get_admin_network_group().id] = \
            seed_cluster.get_admin_network_group().id
        return mapping

    @classmethod
    def get_nodegroups_id_mapping(cls, orig_cluster, seed_cluster):
        orig_ng = orig_cluster.node_groups
        seed_ng = seed_cluster.node_groups

        seed_ng_dict = dict((ng.name, ng.id) for ng in seed_ng)
        mapping = dict((ng.id, seed_ng_dict[ng.name]) for ng in orig_ng)
        return mapping
