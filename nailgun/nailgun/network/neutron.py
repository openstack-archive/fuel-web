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

import six

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import NeutronConfig

from nailgun.network.manager import AllocateVIPs70Mixin
from nailgun.network.manager import NetworkManager


class NeutronManager(NetworkManager):

    @classmethod
    def create_neutron_config(
            cls, cluster, segmentation_type,
            net_l23_provider=consts.NEUTRON_L23_PROVIDERS.ovs):
        neutron_config = NeutronConfig(
            cluster_id=cluster.id,
            segmentation_type=segmentation_type,
            net_l23_provider=net_l23_provider
        )
        db().add(neutron_config)
        meta = cluster.release.networks_metadata["neutron"]["config"]
        for key, value in meta.iteritems():
            if hasattr(neutron_config, key):
                setattr(neutron_config, key, value)
        db().flush()

    @classmethod
    def generate_vlan_ids_list(cls, data, cluster, ng):
        if ng.get("name") == consts.NETWORKS.private and \
                cluster.network_config.segmentation_type == \
                consts.NEUTRON_SEGMENT_TYPES.vlan:
            if data.get("networking_parameters", {}).get("vlan_range"):
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


class NeutronManager70(AllocateVIPs70Mixin, NeutronManager):

    @classmethod
    def build_role_to_network_group_mapping(cls, cluster, node_group_name):
        """Builds network role to network map according to template data if
        template is loaded. Otherwise, empty map is returned.

        :param cluster: Cluster instance
        :type cluster: Cluster model
        :param node_group_name: Node group name
        :type  node_group_name: string
        :return: Network role to network map
        :rtype: dict
        """
        template = cluster.network_config.configuration_template
        if template is None:
            return {}

        node_group = template['adv_net_template'][node_group_name]
        endpoint_to_net_group = {}
        for net_group, value in six.iteritems(
                node_group['network_assignments']):
            endpoint_to_net_group[value['ep']] = net_group

        result = {}
        for scheme in six.itervalues(node_group['network_scheme']):
            for role, endpoint in six.iteritems(scheme['roles']):
                if endpoint in endpoint_to_net_group:
                    result[role] = endpoint_to_net_group[endpoint]

        return result

    @classmethod
    def get_network_group_for_role(cls, network_role, net_group_mapping):
        """Returns network group to which network role is associated.
        If networking template is set first lookup happens in the
        template. Otherwise the default network group from
        the network role is returned.

        :param network_role: Network role dict
        :type network_role: dict
        :param net_group_mapping: Network role to network group mapping
        :type  net_group_mapping: dict
        :return: Network group name
        :rtype: str
        """
        return net_group_mapping.get(
            network_role['id'], network_role['default_mapping'])

    @classmethod
    def get_node_ips(cls, node):
        """Returns node's IP and gateway's IP for each network of
        particular node.
        """
        if not node.group_id:
            return {}

        ngs = db().query(NetworkGroup, IPAddr.ip_addr).\
            filter(NetworkGroup.group_id == node.group_id). \
            filter(IPAddr.network == NetworkGroup.id). \
            filter(IPAddr.node == node.id). \
            all()
        if not ngs:
            return {}

        networks = {}
        for ng, ip in ngs:
            networks[ng.name] = {
                'ip': cls.get_ip_w_cidr_prefix_len(ip, ng),
                'gateway': ng.gateway
            }
        admin_ng = cls.get_admin_network_group(node.id)
        if admin_ng:
            networks[admin_ng.name] = {
                'ip': cls.get_ip_w_cidr_prefix_len(
                    cls.get_admin_ip_for_node(node.id), admin_ng),
                'gateway': admin_ng.gateway
            }
        return networks
