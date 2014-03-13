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
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import NeutronConfig
from nailgun.network.manager import NetworkManager


class NeutronManager(NetworkManager):

    @classmethod
    def create_neutron_config(cls, cluster, segment_type):
        neutron_config = NeutronConfig(
            cluster_id=cluster.id,
            segmentation_type=segment_type,
        )
        db().add(neutron_config)
        meta = cluster.release.networks_metadata["neutron"]["config"]
        for key, value in meta.iteritems():
            if hasattr(neutron_config, key):
                setattr(neutron_config, key, value)
        db().flush()

    @classmethod
    def _generate_external_network(cls, cluster):
        public_cidr, public_gw = db().query(
            NetworkGroup.cidr,
            NetworkGroup.gateway
        ).filter_by(
            cluster_id=cluster.id,
            name='public'
        ).first()
        join_range = lambda r: (":".join(map(str, r)) if r else None)
        return {
            "L3": {
                "subnet": public_cidr,
                "gateway": public_gw,
                "nameservers": [],
                "floating": join_range(
                    cluster.network_config.external_floating_ranges[0]),
                "enable_dhcp": False
            },
            "L2": {
                "network_type": "flat",
                "segment_id": None,
                "router_ext": True,
                "physnet": "physnet1"
            },
            "tenant": "admin",
            "shared": False
        }

    @classmethod
    def _generate_internal_network(cls, cluster):
        return {
            "L3": {
                "subnet": cluster.network_config.internal_cidr,
                "gateway": cluster.network_config.internal_gateway,
                "nameservers": cluster.network_config.dns_nameservers,
                "floating": None,
                "enable_dhcp": True
            },
            "L2": {
                "network_type": cluster.network_config.segmentation_type,
                "segment_id": None,
                "router_ext": False,
                "physnet": "physnet2"
                if cluster.network_config.segmentation_type == "vlan" else None
            },
            "tenant": "admin",
            "shared": False
        }

    @classmethod
    def generate_predefined_networks(cls, cluster):
        return {
            "net04_ext": cls._generate_external_network(cluster),
            "net04": cls._generate_internal_network(cluster)
        }

    @classmethod
    def generate_l2(cls, cluster):
        join_range = lambda r: (":".join(map(str, r)) if r else None)

        res = {
            "base_mac": cluster.network_config.base_mac,
            "segmentation_type": cluster.network_config.segmentation_type,
            "phys_nets": {
                "physnet1": {
                    "bridge": "br-ex",
                    "vlan_range": None
                }
            }
        }
        if cluster.network_config.segmentation_type == 'gre':
            res["tunnel_id_ranges"] = join_range(
                cluster.network_config.gre_id_range)
        elif cluster.network_config.segmentation_type == 'vlan':
            res["phys_nets"]["physnet2"] = {
                "bridge": "br-prv",
                "vlan_range": join_range(cluster.network_config.vlan_range)
            }
        return res

    @classmethod
    def generate_l3(cls, cluster):
        return {
            "use_namespaces": True
        }

    @classmethod
    def update(cls, cluster, network_configuration):
        cls.update_networks(cluster, network_configuration)

        if 'networking_parameters' in network_configuration:
            for key, value in network_configuration['networking_parameters'] \
                    .items():
                setattr(cluster.network_config, key, value)
            db().commit()

    @classmethod
    def generate_vlan_ids_list(cls, data, cluster, ng):
        if ng.get("name") == "private":
            if "networking_parameters" in data:
                vlan_range = data["networking_parameters"]["vlan_range"]
            else:
                vlan_range = cluster.network_config.vlan_range
            return range(vlan_range[0], vlan_range[1] + 1)
        return [int(ng.get("vlan_start"))] if ng.get("vlan_start") else []

    @classmethod
    def get_ovs_bond_properties(cls, bond):
        props = []
        if 'lacp' in bond.mode:
            props.append('lacp=active')
            props.append('bond_mode=balance-tcp')
        else:
            props.append('bond_mode=%s' % bond.mode)
        return props
