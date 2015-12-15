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

from nailgun import objects
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
    def serialize_net_groups_and_vips(cls, cluster, allocate=False):
        result = {}
        net_manager = objects.Cluster.get_network_manager(cluster)
        nets = cluster.network_groups + [net_manager.get_admin_network_group()]

        result['networks'] = map(
            cls.serialize_network_group,
            nets
        )

        if cluster.is_ha_mode:
            result.update(
                net_manager.assign_vips_for_net_groups_for_api(cluster,
                                                               allocate))

        return result

    @classmethod
    def serialize_network_params(cls, cluster):
        return BasicSerializer.serialize(
            cluster.network_config,
            cls.network_cfg_fields)


class NovaNetworkConfigurationSerializer(NetworkConfigurationSerializer):

    network_cfg_fields = (
        'dns_nameservers',
        'net_manager',
        'fixed_networks_cidr',
        'fixed_networks_vlan_start',
        'fixed_network_size',
        'fixed_networks_amount',
        'floating_ranges',
    )

    @classmethod
    def serialize_for_cluster(cls, cluster, allocate_vips=False):
        result = cls.serialize_net_groups_and_vips(cluster, allocate_vips)
        result['networking_parameters'] = cls.serialize_network_params(
            cluster)
        return result


class NeutronNetworkConfigurationSerializer(NetworkConfigurationSerializer):

    network_cfg_fields = (
        'base_mac',
        'configuration_template',
        'dns_nameservers',
        'floating_name',
        'floating_ranges',
        'gre_id_range',
        'internal_cidr',
        'internal_gateway',
        'internal_name',
        'net_l23_provider',
        'segmentation_type',
        'vlan_range',
    )

    @classmethod
    def serialize_network_params(cls, cluster):
        """Overrides default serialization, adds baremetal fields if need"""
        fields = cls.network_cfg_fields
        if objects.Cluster.is_component_enabled(cluster, 'ironic'):
            fields += ('baremetal_gateway', 'baremetal_range')
        return BasicSerializer.serialize(cluster.network_config, fields)

    @classmethod
    def serialize_for_cluster(cls, cluster, allocate_vips=False):
        result = cls.serialize_net_groups_and_vips(cluster, allocate_vips)
        result['networking_parameters'] = cls.serialize_network_params(cluster)
        return result
