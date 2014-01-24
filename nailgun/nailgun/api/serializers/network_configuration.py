# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from nailgun.api.serializers.base import BasicSerializer
from nailgun.db import db
from nailgun.db.sqlalchemy.models import NodeGroup
from nailgun.network.manager import NetworkManager


class NetworkConfigurationSerializer(BasicSerializer):

    fields = ('id', 'group_id', 'name', 'cidr', 'netmask',
              'gateway', 'vlan_start', 'network_size', 'amount', 'meta')

    @classmethod
    def serialize_network_group(cls, instance, fields=None):
        data_dict = BasicSerializer.serialize(
            instance,
            fields=fields if fields else cls.fields
        )
        data_dict["ip_ranges"] = [
            [ir.first, ir.last] for ir in instance.ip_ranges
        ]
        data_dict.setdefault("netmask", "")
        data_dict.setdefault("gateway", "")
        return data_dict

    @classmethod
    def serialize_net_groups_and_vips(cls, cluster):
        result = {}
        net_manager = NetworkManager
        default_group = db().query(NodeGroup).get(cluster.default_group)
        nets = default_group.networks + [net_manager.get_admin_network_group()]
        result['networks'] = map(
            cls.serialize_network_group,
            nets
        )
        if cluster.is_ha_mode:
            for ng in cluster.network_groups:
                if ng.meta.get("assign_vip"):
                    result['{0}_vip'.format(ng.name)] = \
                        net_manager.assign_vip(cluster.id, ng.name)

        return result


class NovaNetworkConfigurationSerializer(NetworkConfigurationSerializer):

    @classmethod
    def serialize_for_cluster(cls, cluster):
        result = cls.serialize_net_groups_and_vips(cluster)

        result['net_manager'] = cluster.net_manager

        if cluster.dns_nameservers:
            result['dns_nameservers'] = {
                "nameservers": cluster.dns_nameservers
            }

        return result


class NeutronNetworkConfigurationSerializer(NetworkConfigurationSerializer):

    @classmethod
    def serialize_for_cluster(cls, cluster):
        result = cls.serialize_net_groups_and_vips(cluster)

        result['net_provider'] = cluster.net_provider
        result['net_l23_provider'] = cluster.net_l23_provider
        result['net_segment_type'] = cluster.net_segment_type

        result['neutron_parameters'] = {
            'predefined_networks': cluster.neutron_config.predefined_networks,
            'L2': cluster.neutron_config.L2,
            'segmentation_type': cluster.neutron_config.segmentation_type
        }

        return result
