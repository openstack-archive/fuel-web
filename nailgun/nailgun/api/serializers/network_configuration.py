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
from nailgun.network.manager import NetworkManager


class NovaNetworkConfigurationSerializer(BasicSerializer):

    fields = ('id', 'cluster_id', 'name', 'cidr', 'netmask',
              'gateway', 'vlan_start', 'network_size', 'amount')

    @classmethod
    def serialize_network_group(cls, instance, fields=None):
        data_dict = BasicSerializer.serialize(instance, fields=cls.fields)
        data_dict["ip_ranges"] = [
            [ir.first, ir.last] for ir in instance.ip_ranges
        ]
        data_dict.setdefault("netmask", "")
        data_dict.setdefault("gateway", "")
        return data_dict

    @classmethod
    def serialize_for_cluster(cls, cluster):
        result = {}
        result['net_manager'] = cluster.net_manager
        result['networks'] = map(
            cls.serialize_network_group,
            cluster.network_groups
        )
        if cluster.is_ha_mode:
            nw_metadata = cluster.release.networks_metadata["nova_network"]
            net_manager = NetworkManager()
            for network in nw_metadata:
                if network.get("assign_vip") is not False:
                    result['{0}_vip'.format(
                        network["name"]
                    )] = net_manager.assign_vip(
                        cluster.id,
                        network["name"]
                    )
        return result


class NeutronNetworkConfigurationSerializer(BasicSerializer):

    fields = ('id', 'cluster_id', 'name', 'cidr', 'netmask', 'gateway',
              'vlan_start', 'network_size', 'amount')

    @classmethod
    def serialize_network_group(cls, instance, fields=None):
        data_dict = BasicSerializer.serialize(instance, fields=cls.fields)
        data_dict["ip_ranges"] = [
            [ir.first, ir.last] for ir in instance.ip_ranges
        ]
        data_dict.setdefault("netmask", "")
        data_dict.setdefault("gateway", "")
        return data_dict

    @classmethod
    def serialize_for_cluster(cls, cluster):
        result = {}
        result['net_provider'] = cluster.net_provider
        result['net_l23_provider'] = cluster.net_l23_provider
        result['net_segment_type'] = cluster.net_segment_type
        result['networks'] = map(
            cls.serialize_network_group,
            cluster.network_groups
        )
        # result['networks'] = [cls.serialize_network_group(ng)
        #                       for ng in cluster.network_groups
        #                       if ng.name != 'private']

        result['neutron_parameters'] = {
            'predefined_networks': cluster.neutron_config.predefined_networks,
            'L2': cluster.neutron_config.L2,
            'segmentation_type': cluster.neutron_config.segmentation_type
        }
        return result
