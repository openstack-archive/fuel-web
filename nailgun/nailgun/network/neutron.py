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

import itertools
import netaddr
import six

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import NeutronConfig

from nailgun.errors import errors
from nailgun.logger import logger

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

    @classmethod
    def get_endpoints_by_node_roles(cls, node):
        """Returns a set of endpoints for particular node for the case when
        template is loaded. Endpoints are taken from 'endpoints' field
        of templates for every node role.
        """
        endpoints = set()
        template = node.network_template

        for role in node.all_roles:
            role_templates = template['templates_for_node_role'][role]
            for role_template in role_templates:
                endpoints.update(
                    template['templates'][role_template]['endpoints'])

        return endpoints

    @classmethod
    def get_network_mapping_by_node_roles(cls, node):
        """Returns a list of pairs (network, endpoint) for particular node
        for the case when template is loaded. Networks are aggregated for all
        node roles assigned to node. Endpoints are taken from 'endpoints' field
        of templates for every node role and they are mapped to networks from
        'network_assignments' field.
        """
        output = []
        endpoints = cls.get_endpoints_by_node_roles(node)

        mappings = node.network_template['network_assignments']
        for netgroup, endpoint in six.iteritems(mappings):
            if endpoint['ep'] in endpoints:
                output.append((netgroup, endpoint['ep']))

        return output

    @classmethod
    def get_network_name_to_endpoint_mappings(cls, cluster):
        output = {}
        template = cluster.network_config.configuration_template[
            'adv_net_template']

        for ng in cluster.node_groups:
            output[ng.id] = {}
            mappings = template[ng.name]['network_assignments']
            for network, endpoint in six.iteritems(mappings):
                output[ng.id][endpoint['ep']] = network

        return output

    @classmethod
    def _iter_free_ips_filtered(cls, ip_ranges, ips_in_use):
        for ip_range in ip_ranges:
            for ip_addr in ip_range:
                ip_str = str(ip_addr)
                if ip_str not in ips_in_use:
                    yield ip_str

    @classmethod
    def ask_for_free_ips(cls, ip_ranges, ips_in_use, count):
        result = []
        while count > 0:
            free_ips = list(itertools.islice(
                cls._iter_free_ips_filtered(ip_ranges, ips_in_use),
                min(count, 30))
            )
            if not free_ips:
                return result

            ips_in_db = db().query(
                IPAddr.ip_addr
            ).filter(
                IPAddr.ip_addr.in_(free_ips)
            )

            if ips_in_db:
                for ip in ips_in_db:
                    free_ips.pop(ip)

            result.extend(free_ips)
            count -= len(free_ips)

        return result

    @classmethod
    def assign_ips_in_node_group(
            cls, net_id, net_name, node_ids, ip_ranges):

        ips_by_node_id = db().query(
            models.IPAddr.ip_addr,
            models.IPAddr.node
        ).filter_by(
            network=net_id
        )

        nodes_dont_need_ip = set()
        ips_in_use = set()
        for ip_str, node_id in ips_by_node_id:
            ip_addr = netaddr.IPAddress(ip_str)
            for ip_range in ip_ranges:
                if ip_addr in ip_range:
                    nodes_dont_need_ip.add(node_id)
                    ips_in_use.add(ip_str)

        nodes_need_ip = node_ids - nodes_dont_need_ip

        free_ips = cls.ask_for_free_ips(
            ip_ranges, ips_in_use, len(nodes_need_ip))
        if len(free_ips) < len(nodes_need_ip):
            raise errors.OutOfIPs()

        for ip, node_id in zip(free_ips, nodes_need_ip):
            logger.info(
                "Assigning IP for node '{0}' in network '{1}'".format(
                    node_id,
                    net_name
                )
            )
            ip_db = IPAddr(node=node_id,
                           ip_addr=ip,
                           network=net_id)
            db().add(ip_db)
        db().flush()

    @classmethod
    def assign_ips_for_nodes_w_template(cls, cluster, nodes):
        network_by_group = db().query(
            models.NetworkGroup.id,
            models.NetworkGroup.name,
            models.NetworkGroup.meta,
        ).join(
            models.NetworkGroup.nodegroup
        ).filter(
            models.NodeGroup.cluster_id == cluster.id,
            models.NetworkGroup.name != consts.NETWORKS.fuelweb_admin
        )

        ip_ranges_by_network = db().query(
            #models.NetworkGroup.id,
            models.IPAddrRange.first,
            models.IPAddrRange.last,
        ).join(
            models.NetworkGroup.ip_ranges,
            models.NetworkGroup.nodegroup
        ).filter(
            models.NodeGroup.cluster_id == cluster.id
        )

        net_name_by_ep = cls.get_network_name_to_endpoint_mappings(cluster)

        for group_id, nodes_in_group in itertools.groupby(
                nodes, lambda n: n.group_id):

            net_names = net_name_by_ep[group_id]
            net_names_by_node = {}
            for node in nodes_in_group:
                eps = cls.get_endpoints_by_node_roles(node)
                net_names_by_node[node.id] = set(net_names[ep] for ep in eps)

            networks = network_by_group.filter(
                models.NetworkGroup.group_id == group_id)
            for net_id, net_name, net_meta in networks:
                if not net_meta.get('notation'):
                    continue
                node_ids = set(node_id
                               for node_id, net_names
                               in six.iteritems(net_names_by_node)
                               if net_name in net_names)
                ip_ranges_ng = ip_ranges_by_network.filter(
                    models.IPAddrRange.network_group_id == net_id
                )
                ip_ranges = [netaddr.IPRange(first, last)
                             for first, last in ip_ranges_ng]

                cls.assign_ips_in_node_group(
                    net_id, net_name, node_ids, ip_ranges)

        cls.assign_admin_ips(nodes)
