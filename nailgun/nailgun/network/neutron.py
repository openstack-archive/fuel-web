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

from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import NeutronConfig
from nailgun.network.manager import NetworkManager


class NeutronManager(NetworkManager):

    @classmethod
    def create_neutron_config(cls, cluster):
        meta = cluster.release.networks_metadata["neutron"]["config"]
        neutron_config = NeutronConfig(
            cluster_id=cluster.id,
            parameters=meta["parameters"],
            predefined_networks=cls._generate_predefined_networks(cluster),
            L2=cls._generate_l2(cluster),
            L3=cls._generate_l3(cluster),
            segmentation_type=cluster.net_segment_type,
        )
        db().add(neutron_config)
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
        net = IPNetwork(public_cidr)
        return {
            "L3": {
                "cidr": public_cidr,
                "gateway": public_gw,
                "nameservers": [],
                "floating": [
                    str(net[len(net) / 2 + 2]),
                    str(net[-2])
                ]
            }
        }

    @classmethod
    def _generate_internal_network(cls, cluster):
        return {
            "L3": {
                "cidr": "192.168.111.0/24",
                "gateway": "192.168.111.1",
                "nameservers": [
                    "8.8.4.4",
                    "8.8.8.8"
                ],
                "floating": []
            }
        }

    @classmethod
    def _generate_predefined_networks(cls, cluster):
        return {
            "net04_ext": cls._generate_external_network(cluster),
            "net04": cls._generate_internal_network(cluster)
        }

    @classmethod
    def _generate_l2(cls, cluster):
        res = {
            "base_mac": "fa:16:3e:00:00:00",
            "segmentation_type": cluster.net_segment_type,
            "phys_nets": {
                "physnet1": {
                    "bridge": "br-ex",
                    "vlan_range": []
                },
                "physnet2": {
                    "bridge": "br-prv",
                    "vlan_range": []
                }
            }
        }
        if cluster.net_segment_type == 'gre':
            res["tunnel_id_ranges"] = [2, 65535]
        elif cluster.net_segment_type == 'vlan':
            res["phys_nets"]["physnet2"]["vlan_range"] = [
                1000,
                1030
            ]
        return res

    @classmethod
    def _generate_l3(cls, cluster):
        return {}

    @classmethod
    def get_allowed_nic_networkgroups(cls, node, nic):
        """Get all allowed network groups
        """
        if nic == node.admin_interface:
            return [cls.get_admin_network_group()]
        return cls.get_all_cluster_networkgroups(node)

    @classmethod
    def allow_network_assignment_to_all_interfaces(cls, node):
        """Method adds all network groups from cluster
        to allowed_networks list for all interfaces
        of specified node.

        :param node: Node object.
        :type  node: Node
        """
        for nic in node.interfaces:

            if nic == node.admin_interface:
                nic.allowed_networks_list.append(
                    cls.get_admin_network_group()
                )
                continue

            for ng in cls.get_cluster_networkgroups_by_node(node):
                nic.allowed_networks_list.append(ng)

        db().commit()

    @classmethod
    def get_default_networks_assignment(cls, node):
        """Assign all network groups except admin to one NIC,
        admin network group has its own NIC by default - gre
        Assign all network groups except admin and private to one NIC,
        admin and private network groups has their own NICs by default - vlan
        """
        nics = []
        to_be_assigned = set([ng.name for ng in node.cluster.network_groups] +
                             [cls.get_admin_network_group().name])
        for i, nic in enumerate(node.interfaces):
            nic_dict = {
                "id": nic.id,
                "name": nic.name,
                "mac": nic.mac,
                "max_speed": nic.max_speed,
                "current_speed": nic.current_speed
            }
            if to_be_assigned:
                if nic == node.admin_interface:
                    admin_ng = cls.get_admin_network_group()
                    assigned_ngs = [admin_ng]
                else:
                    if node.cluster.net_segment_type == 'vlan':
                        if "public" in to_be_assigned:
                            assigned_ngs = filter(
                                lambda ng: ng.name != "private",
                                node.cluster.network_groups)
                        else:
                            assigned_ngs = filter(
                                lambda ng: ng.name == "private",
                                node.cluster.network_groups)
                    else:
                        assigned_ngs = [ng
                                        for ng in node.cluster.network_groups]

                for ng in assigned_ngs:
                    nic_dict.setdefault('assigned_networks', []).append(
                        {'id': ng.id, 'name': ng.name})
                to_be_assigned -= set([ng.name for ng in assigned_ngs])

            allowed_ngs = cls.get_allowed_nic_networkgroups(
                node,
                nic
            )

            for ng in allowed_ngs:
                nic_dict.setdefault('allowed_networks', []).append(
                    {'id': ng.id, 'name': ng.name})

            nics.append(nic_dict)
        return nics

    @classmethod
    def update(cls, cluster, network_configuration):
        cls.update_networks(cluster, network_configuration)

        if 'neutron_parameters' in network_configuration:
            if 'networks' in network_configuration:
                #TODO(NAME) get rid of unmanaged parameters in request
                for ng in network_configuration['networks']:
                    if ng['name'] == 'public':
                        pre_nets = network_configuration[
                            'neutron_parameters']['predefined_networks']
                        pre_nets['net04_ext']['L3']['gateway'] = ng['gateway']
            for key, value in network_configuration['neutron_parameters'] \
                    .items():
                setattr(cluster.neutron_config, key, value)
            db().add(cluster.neutron_config)
            db().commit()

    @classmethod
    def generate_vlan_ids_list(cls, data, cluster, ng):
        if ng.get("name") == "private":
            if "neutron_parameters" in data:
                l2params = data["neutron_parameters"]["L2"]
            else:
                l2params = cluster.neutron_config.L2
            vlan_range = l2params["phys_nets"]["physnet2"]["vlan_range"]
            return range(vlan_range[0], vlan_range[1] + 1)
        return [int(ng.get("vlan_start"))] if ng.get("vlan_start") else []
