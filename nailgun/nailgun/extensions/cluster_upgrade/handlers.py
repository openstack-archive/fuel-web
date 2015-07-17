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

from nailgun.api.v1.handlers import base
from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import objects
from nailgun.objects.serializers import network_configuration
from nailgun import utils

from . import validators


class ClusterUpgradeHandler(base.BaseHandler):
    single = objects.Cluster
    validator = validators.ClusterUpgradeValidator
    network_serializers = {
        consts.CLUSTER_NET_PROVIDERS.neutron:
        network_configuration.NeutronNetworkConfigurationSerializer,
        consts.CLUSTER_NET_PROVIDERS.nova_network:
        network_configuration.NovaNetworkConfigurationSerializer,
    }

    @base.content
    def POST(self, cluster_id):
        from . import upgrade

        request_data = self.checked_data()
        release_id = request_data['release_id']
        new_cluster_name = request_data['name']

        orig_cluster = self.get_object_or_404(self.single, cluster_id)
        release = self.get_object_or_404(objects.Release, release_id)

        self.validator.validate_cluster_status(orig_cluster)
        self.validator.validate_cluster_name(new_cluster_name)
        self.validator.validate_release_upgrade(orig_cluster.release, release)

        data = {
            "name": new_cluster_name,
            "mode": orig_cluster.mode,
            "status": consts.CLUSTER_STATUSES.new,
            "net_provider": orig_cluster.net_provider,
            "grouping": consts.CLUSTER_GROUPING.roles,
            "release_id": release.id,
        }
        if orig_cluster.net_provider == consts.CLUSTER_NET_PROVIDERS.neutron:
            data["net_segment_type"] = \
                orig_cluster.network_config.segmentation_type
            data["net_l23_provider"] = \
                orig_cluster.network_config.net_l23_provider
        new_cluster = self.single.create(data)
        new_cluster.attributes.generated = utils.dict_merge(
            new_cluster.attributes.generated,
            orig_cluster.attributes.generated)
        new_cluster.attributes.editable = self.merge_attributes(
            orig_cluster.attributes.editable,
            new_cluster.attributes.editable)
        nets_serializer = self.network_serializers[orig_cluster.net_provider]
        nets = self.merge_nets(
            nets_serializer.serialize_for_cluster(orig_cluster),
            nets_serializer.serialize_for_cluster(new_cluster))
        net_manager = self.single.get_network_manager(instance=new_cluster)
        net_manager.update(new_cluster, nets)
        self.copy_vips(orig_cluster, new_cluster)
        net_manager.assign_vips_for_net_groups(new_cluster)
        upgrade.create_clusters_upgrade_relation(orig_cluster,
                                                 new_cluster)
        db.commit()
        return self.single.to_json(new_cluster)

    @staticmethod
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
        db.commit()

    @staticmethod
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

    @classmethod
    def merge_nets(cls, a, b):
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
