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

from netaddr import IPNetwork

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import NovaNetworkConfig
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

        # We need set maximum available size for specific mask for FlatDHCP
        # because default 256 caused problem and we don't have possibilities
        # to modified it via UI
        if nova_net_config.net_manager ==\
           consts.NOVA_NET_MANAGERS.FlatDHCPManager:
            net_cidr = IPNetwork(nova_net_config.fixed_networks_cidr)
            nova_net_config.fixed_network_size = net_cidr.size
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

    @classmethod
    def update(cls, cluster, network_configuration):
        cls.update_networks(cluster, network_configuration)

        if 'networking_parameters' in network_configuration:
            network_params = network_configuration['networking_parameters']

            # We must check if we need calculate network size for FlatDHCP
            if ((network_params.get('fixed_networks_cidr') or
                network_params.get('fixed_network_size')) and
                (consts.NOVA_NET_MANAGERS.FlatDHCPManager ==
                network_params.get(
                    'net_manager',
                    cluster.network_config['net_manager']))):

                net_cidr = IPNetwork(
                    network_params.get('fixed_networks_cidr') or
                    cluster.network_config['fixed_networks_cidr'])
                network_params['fixed_network_size'] = net_cidr.size

            for key, value in network_params.items():
                setattr(cluster.network_config, key, value)
            db().flush()
