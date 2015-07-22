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
from nailgun.db.sqlalchemy.models import NeutronConfig
from nailgun.errors import errors
from nailgun import objects

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
    def _get_role_endpoint(cls, role_id, network_scheme):
        for scheme in six.itervalues(network_scheme):
            for role, endpoint in six.iteritems(scheme['roles']):
                if role == role_id:
                    return endpoint

    @classmethod
    def get_network_group_for_role(cls, cluster, network_role):
        """Returns network group to which network role is associated.
        If networking template is set first lookup happens in the
        template. Otherwise the default network group from
        the network role is returned.

        :param network_role: Network role dict
        :type network_role: dict
        :return: Network group name
        :rtype: str
        """
        default_net_group = network_role['default_mapping']
        template = cluster.network_config.configuration_template
        if template is None:
            return default_net_group

        group_id = objects.Cluster.get_controllers_group_id(cluster)
        node_group_db = objects.NodeGroup.get_by_uid(group_id)

        net_template = template['adv_net_template']
        node_group = net_template[node_group_db.name]
        network_scheme = node_group['network_scheme']

        role_endpoint = cls._get_role_endpoint(
            network_role['id'], network_scheme)
        if role_endpoint is None:
            return default_net_group

        net_assignments = node_group['network_assignments']
        for net_group, value in six.iteritems(net_assignments):
            if value['ep'] == role_endpoint:
                return net_group

        return default_net_group

    @classmethod
    def find_network_role_by_id(cls, cluster, role_id):
        """Returns network role for specified role id.

        :param cluster: Cluster instance
        :param role_id: Network role id
        :type role_id: str
        :return: Network role dict or None if not found
        """
        net_roles = objects.Cluster.get_network_roles(cluster)
        for role in net_roles:
            if role['id'] == role_id:
                return role
        return None

    @classmethod
    def get_end_point_ip(cls, cluster_id):
        cluster_db = objects.Cluster.get_by_uid(cluster_id)
        net_role = cls.find_network_role_by_id(cluster_db, 'public/vip')
        if net_role:
            net_group = cls.get_network_group_for_role(cluster_db, net_role)
            return cls.assign_vip(cluster_db, net_group, vip_type='public')
        else:
            raise errors.CanNotDetermineEndPointIP(
                u'Can not determine end point IP for cluster %s' %
                cluster_db.full_name)

    @classmethod
    def _assign_vips_for_net_groups(cls, cluster):
        net_roles = objects.Cluster.get_network_roles(cluster)
        for role in net_roles:
            properties = role.get('properties', {})
            net_group = cls.get_network_group_for_role(cluster, role)
            for vip_info in properties.get('vip', ()):
                vip_name = vip_info['name']
                vip_addr = cls.assign_vip(
                    cluster, net_group, vip_type=vip_name)

                yield role, vip_info, vip_addr

    @classmethod
    def assign_vips_for_net_groups_for_api(cls, cluster):
        """Calls cls.assign_vip for all vips in network roles.
        Returns dict with vip definitions in API compatible format::

            {
                "vip_alias": "172.16.0.1"
            }

        :param cluster: Cluster instance
        :type  cluster: Cluster model
        :return: dict with vip definitions
        """
        vips = {}
        for role, vip_info, vip_addr in cls._assign_vips_for_net_groups(
                cluster):
            alias = vip_info.get('alias')
            if alias:
                vips[alias] = vip_addr

        return vips

    @classmethod
    def assign_vips_for_net_groups(cls, cluster):
        """Calls cls.assign_vip for all vips in network roles.
        To be used for the output generation for orchestrator.
        Returns dict with vip definitions like::

            {
                "vip_name": {
                    "network_role": "public",
                    "namespace": "haproxy",
                    "ipaddr": "172.16.0.1"
                }
            }

        :param cluster: Cluster instance
        :type  cluster: Cluster model
        :return: dict with vip definitions
        """
        vips = {}
        for role, vip_info, vip_addr in cls._assign_vips_for_net_groups(
                cluster):
            vip_name = vip_info['name']
            vips[vip_name] = {
                'network_role': role['id'],
                'namespace': vip_info.get('namespace'),
                'ipaddr': vip_addr,
            }

        return vips
