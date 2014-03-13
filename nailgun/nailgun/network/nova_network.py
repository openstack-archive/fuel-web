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
    def update(cls, cluster, network_configuration):
        cls.update_networks(cluster, network_configuration)

        if 'nova_network_parameters' in network_configuration:
            for key, value in network_configuration['nova_network_parameters']\
                    .items():
                setattr(cluster.network_config, key, value)
            db().commit()

    @classmethod
    def generate_vlan_ids_list(cls, data, cluster, ng):
        if ng.get("vlan_start") is None:
            return []
        return [int(ng.get("vlan_start"))]
