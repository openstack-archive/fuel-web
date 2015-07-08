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

from nailgun import consts
from nailgun import objects
from nailgun.db import db
from nailgun.db.sqlalchemy.models import NeutronConfig
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


class NeutronManager70(NeutronManager):

    @classmethod
    def roles_to_ifaces(cls):
        return {consts.NETWORKS.fuelweb_admin: 'br-fw-admin',
                consts.NETWORKS.storage: 'br-storage',
                consts.NETWORKS.management: 'br-mgmt',
                consts.NETWORKS.public: 'br-ex'}

    @classmethod
    def roles_to_ips(cls, node):
        mapping = {}
        for net in cls.roles_to_ifaces():
            netgroup = cls.get_node_network_by_netname(node, net)
            if netgroup.get('ip'):
                mapping[net] = netgroup['ip'].split('/')[0]
        return mapping

    @classmethod
    def map_roles(cls, node, to_interfaces=False):
        if to_interfaces:
            mapping = cls.roles_to_ifaces()
        else:
            mapping = cls.roles_to_ips(node)

        roles = {}
        for role in objects.Cluster.get_network_roles(node.cluster):
            roles[role['id']] = \
                mapping.get(role['default_mapping'], mapping[consts.NETWORKS.management])

        if objects.Node.should_have_public(node):
            roles['ex'] = mapping[consts.NETWORKS.public]  # not needed
            roles['public/vip'] = mapping[consts.NETWORKS.public]
            roles['ceph/radosgw'] = mapping[consts.NETWORKS.public]

        return roles
