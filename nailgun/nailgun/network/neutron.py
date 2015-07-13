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

import re

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
    def get_network_group_by_role(cls, network_role):
        return network_role['default_mapping']

    @classmethod
    def assign_vips_for_net_groups(cls, cluster):
        net_roles = objects.Cluster.get_network_roles(cluster)
        vips = {}

        for role in net_roles:
            properties = role.get('properties', {})
            net_group = cls.get_network_group_by_role(role)
            for vip_info in properties.get('vip', ()):
                vip_name = cls._sanitize_vip_name(vip_info['name'])
                vip_addr = cls.assign_vip(
                    cluster, net_group, vip_type=vip_name)

                vips[vip_name] = {
                    'network_role': role['id'],
                    'namespace': vip_info.get('namespace', vip_name),
                    'ipaddr': vip_addr,
                }

        return vips

    @classmethod
    def _sanitize_vip_name(cls, vip_name):
        vip_name = vip_name.lower().replace('\_', '_')
        vip_name = re.sub(r'[^a-z_]', '_', vip_name)
        vip_name = vip_name.strip('_')
        return vip_name
