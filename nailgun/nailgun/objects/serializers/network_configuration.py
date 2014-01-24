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

from nailgun.network.manager import NetworkManager
from nailgun.objects.serializers.base import BasicSerializer


class NetworkConfigurationSerializer(BasicSerializer):

    fields = ('id', 'group_id', 'name', 'cidr',
              'gateway', 'vlan_start', 'meta')

    @classmethod
    def serialize_network_group(cls, instance, fields=None):
        data_dict = BasicSerializer.serialize(
            instance,
            fields=fields if fields else cls.fields
        )
        data_dict["ip_ranges"] = [
            [ir.first, ir.last] for ir in instance.ip_ranges
        ]
        data_dict.setdefault("gateway", "")
        return data_dict

    @classmethod
    def serialize_net_groups_and_vips(cls, cluster):
        result = {}
        net_manager = NetworkManager
        nets = cluster.network_groups + [net_manager.get_admin_network_group()]

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

    @classmethod
    def serialize_network_params(cls, cluster):
        return BasicSerializer.serialize(
            cluster.network_config,
            cls.network_cfg_fields)


class NovaNetworkConfigurationSerializer(NetworkConfigurationSerializer):

    network_cfg_fields = (
        'dns_nameservers', 'net_manager', 'fixed_networks_cidr',
        'fixed_networks_vlan_start', 'fixed_network_size',
        'fixed_networks_amount', 'floating_ranges')

    @classmethod
    def serialize_for_cluster(cls, cluster):
        result = cls.serialize_net_groups_and_vips(cluster)
        result['networking_parameters'] = cls.serialize_network_params(
            cluster)
        return result


class NeutronNetworkConfigurationSerializer(NetworkConfigurationSerializer):

    network_cfg_fields = (
        'dns_nameservers', 'segmentation_type', 'net_l23_provider',
        'floating_ranges', 'vlan_range', 'gre_id_range',
        'base_mac', 'internal_cidr', 'internal_gateway')

    @classmethod
    def serialize_for_cluster(cls, cluster):
        result = cls.serialize_net_groups_and_vips(cluster)
        result['networking_parameters'] = cls.serialize_network_params(cluster)
        return result
