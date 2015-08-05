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

from nailgun.db import db
from nailgun.db.sqlalchemy.models import NovaNetworkConfig

from nailgun.network.manager import AllocateVIPs70Mixin
from nailgun.network.manager import NetworkManager


class NovaNetworkManager(NetworkManager):

    @classmethod
    def create_nova_network_config(cls, cluster):
        nova_net_config = NovaNetworkConfig(
            cluster_id=cluster.id,
        )
        db().add(nova_net_config)
        meta = cluster.release.networks_metadata["nova_network"]["config"]
        for key, value in meta.iteritems():
            if hasattr(nova_net_config, key):
                setattr(nova_net_config, key, value)
        db().flush()

    @classmethod
    def generate_vlan_ids_list(cls, data, cluster, ng):
        if ng["name"] == "fixed":
            netw_params = data.get("networking_parameters", {})
            start = netw_params.get("fixed_networks_vlan_start")
            amount = netw_params.get("fixed_networks_amount")
            if start and amount:
                return range(int(start), int(start) + int(amount))
        if ng.get("vlan_start") is None:
            return []
        return [int(ng.get("vlan_start"))]


class NovaNetworkManager70(AllocateVIPs70Mixin, NovaNetworkManager):

    @classmethod
    def build_role_to_network_group_mapping(cls, *_):
        """Default network role to network mapping is used always so
        map building is not required.

        :return: Empty network role to network map
        :rtype: dict
        """
        return {}

    @classmethod
    def get_network_group_for_role(cls, network_role, _):
        """Returns network group to which network role is associated.
        The default network group from the network role description is
        returned.

        :param network_role: Network role dict
        :type network_role: dict
        :return: Network group name
        :rtype: str
        """
        return network_role['default_mapping']
