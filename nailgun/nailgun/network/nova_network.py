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
from nailgun.network.manager import NetworkManager


class NovaNetworkManager(NetworkManager):

    @classmethod
    def get_default_networks_assignment(cls, node):
        nics = []
        for nic in node.interfaces:
            nic_dict = {
                "id": nic.id,
                "name": nic.name,
                "mac": nic.mac,
                "max_speed": nic.max_speed,
                "current_speed": nic.current_speed
            }

            assigned_ngs = cls.get_default_nic_networkgroups(
                node, nic)

            for ng in assigned_ngs:
                nic_dict.setdefault('assigned_networks', []).append(
                    {'id': ng.id, 'name': ng.name})

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
    def get_default_nic_networkgroups(cls, node, nic):
        """Assign all network groups except admin to one NIC,
        admin network group has its own NIC by default
        """
        if len(node.interfaces) < 2:
            return (
                [cls.get_admin_network_group()] +
                cls.get_all_cluster_networkgroups(node)
            ) if nic == node.admin_interface else []

        if nic == node.admin_interface:
            return [cls.get_admin_network_group()]
        # return get_all_cluster_networkgroups() for the first non-admin NIC
        # and [] for other NICs
        for n in node.interfaces:
            if n == nic:
                return cls.get_all_cluster_networkgroups(node)
            if n != node.admin_interface:
                return []

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

            for ng in cls.get_cluster_networkgroups_by_node(node):
                nic.allowed_networks_list.append(ng)

        db().commit()

    @classmethod
    def get_allowed_nic_networkgroups(cls, node, nic):
        """Get all allowed network groups
        """
        ngs = cls.get_all_cluster_networkgroups(node)
        if nic == node.admin_interface:
            ngs.append(cls.get_admin_network_group())
        return ngs

    @classmethod
    def update(cls, cluster, network_configuration):
        cls.update_networks(cluster, network_configuration)

        if 'net_manager' in network_configuration:
            setattr(
                cluster,
                'net_manager',
                network_configuration['net_manager']
            )
        if 'dns_nameservers' in network_configuration:
            setattr(
                cluster,
                'dns_nameservers',
                network_configuration['dns_nameservers']['nameservers']
            )
        db().commit()

    @classmethod
    def generate_vlan_ids_list(cls, data, cluster, ng):
        if ng.get("vlan_start") is None:
            return []
        return range(int(ng.get("vlan_start")),
                     int(ng.get("vlan_start")) + int(ng.get("amount")))
