# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

"""Neutron network deployment serializers for orchestrator"""

from collections import defaultdict
import netaddr
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import re
import six

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator.base_serializers import MellanoxMixin
from nailgun.orchestrator.base_serializers import NetworkDeploymentSerializer
from nailgun.settings import settings
from nailgun import utils


class NeutronNetworkDeploymentSerializer(
    NetworkDeploymentSerializer,
    MellanoxMixin
):

    @classmethod
    def network_provider_cluster_attrs(cls, cluster):
        """Cluster attributes."""
        attrs = {'quantum': True,
                 'quantum_settings': cls.neutron_attrs(cluster)}

        if cluster.mode == 'multinode':
            for node in cluster.nodes:
                if cls._node_has_role_by_name(node, 'controller'):
                    net_manager = objects.Cluster.get_network_manager(cluster)
                    networks = net_manager.get_node_networks(node)
                    mgmt_cidr = net_manager.get_network_by_netname(
                        'management', networks)['ip']
                    attrs['management_vip'] = mgmt_cidr.split('/')[0]
                    break

        return attrs

    @classmethod
    def network_provider_node_attrs(cls, cluster, node):
        """Serialize node, then it will be merged with common attributes."""
        nm = objects.Cluster.get_network_manager(cluster)
        networks = nm.get_node_networks(node)
        node_attrs = {
            'network_scheme': cls.generate_network_scheme(node, networks)
        }

        cls.inject_mellanox_settings_for_deployment(
            node_attrs, cluster, networks)

        return node_attrs

    @classmethod
    def _node_has_role_by_name(cls, node, rolename):
        if rolename in node.pending_roles or rolename in node.roles:
            return True
        return False

    @classmethod
    def neutron_attrs(cls, cluster):
        """Network configuration for Neutron."""
        internal_name = cluster.network_config.internal_name
        floating_name = cluster.network_config.floating_name

        attrs = {
            'L3': cls.generate_l3(cluster),
            'L2': cls.generate_l2(cluster),
            'predefined_networks': cls.generate_predefined_networks(cluster),

            'default_private_net': internal_name,
            'default_floating_net': floating_name,
        }

        if cluster.release.operating_system == 'RHEL':
            attrs['amqp'] = {'provider': 'qpid-rh'}

        cluster_attrs = objects.Cluster.get_editable_attributes(cluster)
        if 'nsx_plugin' in cluster_attrs and \
                cluster_attrs['nsx_plugin']['metadata']['enabled']:
            attrs['L2']['provider'] = 'nsx'

        return attrs

    @classmethod
    def generate_network_scheme(cls, node, networks):

        # Create a data structure and fill it with static values.

        attrs = {
            'version': '1.0',
            'provider': 'ovs',
            'interfaces': {},  # It's a list of physical interfaces.
            'endpoints': {
                'br-storage': {},
                'br-mgmt': {},
                'br-fw-admin': {},
            },
            'roles': {
                'management': 'br-mgmt',
                'storage': 'br-storage',
                'fw-admin': 'br-fw-admin',
            },
            'transformations': []
        }

        if objects.Node.should_have_public(node):
            attrs['endpoints']['br-ex'] = {}
            attrs['roles']['ex'] = 'br-ex'

        nm = objects.Cluster.get_network_manager(node.cluster)
        iface_types = consts.NETWORK_INTERFACE_TYPES

        # Add a dynamic data to a structure.

        vlan_splinters_data = \
            node.cluster.attributes.editable\
            .get('vlan_splinters', {})\

        # if vlan_splinters is enabled - use its value
        use_vlan_splinters = 'disabled'
        if vlan_splinters_data\
                .get('metadata', {})\
                .get('enabled'):

            use_vlan_splinters = \
                vlan_splinters_data\
                .get('vswitch', {})\
                .get('value', 'disabled')

        # Fill up interfaces and add bridges for them.
        bonded_ifaces = [x for x in node.nic_interfaces if x.bond]
        for iface in node.interfaces:
            # Handle vlan splinters.
            if iface.type == iface_types.ether:
                attrs['interfaces'][iface.name] = {
                    'L2': cls._get_vlan_splinters_desc(
                        use_vlan_splinters, iface, node.cluster
                    )
                }

            if iface in bonded_ifaces:
                continue
            attrs['transformations'].append({
                'action': 'add-br',
                'name': 'br-%s' % iface.name
            })
            if iface.type == iface_types.ether:
                attrs['transformations'].append({
                    'action': 'add-port',
                    'bridge': 'br-%s' % iface.name,
                    'name': iface.name
                })
            elif iface.type == iface_types.bond:
                attrs['transformations'].append({
                    'action': 'add-bond',
                    'bridge': 'br-%s' % iface.name,
                    'name': iface.name,
                    'interfaces': [x['name'] for x in iface.slaves],
                    'properties': nm.get_ovs_bond_properties(iface)
                })

        # Add bridges for networks.
        # We have to add them after br-ethXX bridges because it is the way
        # to provide a right ordering of ifdown/ifup operations with
        # IP interfaces.
        brnames = ['br-ex', 'br-mgmt', 'br-storage', 'br-fw-admin']
        if not objects.Node.should_have_public(node):
            brnames.pop(0)

        for brname in brnames:
            attrs['transformations'].append({
                'action': 'add-br',
                'name': brname
            })

        # Populate IP address information to endpoints.
        netgroup_mapping = [
            ('storage', 'br-storage'),
            ('management', 'br-mgmt'),
            ('fuelweb_admin', 'br-fw-admin'),
        ]
        if objects.Node.should_have_public(node):
            netgroup_mapping.append(('public', 'br-ex'))

        netgroups = {}
        for ngname, brname in netgroup_mapping:
            # Here we get a dict with network description for this particular
            # node with its assigned IPs and device names for each network.
            netgroup = nm.get_network_by_netname(ngname, networks)
            if netgroup.get('ip'):
                attrs['endpoints'][brname]['IP'] = [netgroup['ip']]
            netgroups[ngname] = netgroup

        if objects.Node.should_have_public(node):
            attrs['endpoints']['br-ex']['gateway'] = \
                netgroups['public']['gateway']
        else:
            attrs['endpoints']['br-fw-admin']['gateway'] = settings.MASTER_IP

        # Connect interface bridges to network bridges.
        for ngname, brname in netgroup_mapping:
            netgroup = nm.get_network_by_netname(ngname, networks)
            if not netgroup['vlan']:
                # Untagged network.
                attrs['transformations'].append({
                    'action': 'add-patch',
                    'bridges': ['br-%s' % netgroup['dev'], brname],
                    'trunks': [0]
                })
            elif netgroup['vlan'] > 1:
                # Tagged network.
                attrs['transformations'].append({
                    'action': 'add-patch',
                    'bridges': ['br-%s' % netgroup['dev'], brname],
                    'tags': [netgroup['vlan'], 0]
                })
            else:
                # FIXME! Should raise some exception I think.
                logger.error('Invalid vlan for network: %s' % str(netgroup))

        # Dance around Neutron segmentation type.
        if node.cluster.network_config.segmentation_type == \
                consts.NEUTRON_SEGMENT_TYPES.vlan:
            attrs['endpoints']['br-prv'] = {'IP': 'none'}
            attrs['roles']['private'] = 'br-prv'

            attrs['transformations'].append({
                'action': 'add-br',
                'name': 'br-prv',
            })

            attrs['transformations'].append({
                'action': 'add-patch',
                'bridges': [
                    'br-%s' % objects.Node.get_interface_by_net_name(
                        node.id,
                        'private'
                    ).name,
                    'br-prv'
                ]
            })
        elif node.cluster.network_config.segmentation_type in \
                (consts.NEUTRON_SEGMENT_TYPES.gre,
                 consts.NEUTRON_SEGMENT_TYPES.tun):
            attrs['roles']['mesh'] = 'br-mgmt'

        return attrs

    @classmethod
    def _get_vlan_splinters_desc(cls, use_vlan_splinters, iface,
                                 cluster):
        iface_attrs = {}
        if use_vlan_splinters in ('disabled', 'kernel_lt'):
            iface_attrs['vlan_splinters'] = 'off'
            return iface_attrs
        iface_attrs['vlan_splinters'] = 'auto'
        trunks = [0]

        if use_vlan_splinters == 'hard':
            for ng in iface.assigned_networks_list:
                if ng.name == 'private' and \
                    cluster.network_config.segmentation_type == \
                        consts.NEUTRON_SEGMENT_TYPES.vlan:
                    vlan_range = cluster.network_config.vlan_range
                    trunks.extend(xrange(*vlan_range))
                    trunks.append(vlan_range[1])
                else:
                    if ng.vlan_start in (0, None):
                        continue
                    trunks.append(ng.vlan_start)
        elif use_vlan_splinters == 'soft':
            pass
        else:
            logger.warn('Invalid vlan_splinters value: %s', use_vlan_splinters)
            return {}

        iface_attrs['trunks'] = trunks

        return iface_attrs

    @classmethod
    def render_floating_ranges(cls, floating_ranges):
        """Renders floating IP ranges for external networks generator.

        :param floating_ranges: a list of strings
        :return: rendered string
        """
        return utils.join_range(floating_ranges[0])

    @classmethod
    def generate_external_network(cls, cluster):
        floating_ranges = cluster.network_config.floating_ranges
        floating_iprange = netaddr.IPRange(
            floating_ranges[0][0], floating_ranges[0][1])

        floating_cidr, floating_gw = None, None
        networks = db().query(
            models.NetworkGroup.cidr,
            models.NetworkGroup.gateway
        ).join(
            models.NetworkGroup.nodegroup
        ).filter(
            models.NodeGroup.cluster_id == cluster.id
        )
        for net in networks:
            if net[0] and floating_iprange in netaddr.IPNetwork(net[0]):
                floating_cidr, floating_gw = net[0], net[1]
                break

        return {
            "L3": {
                "subnet": floating_cidr,
                "gateway": floating_gw,
                "nameservers": [],
                "floating": cls.render_floating_ranges(floating_ranges),
                "enable_dhcp": False
            },
            "L2": {
                "network_type": "flat",
                "segment_id": None,
                "router_ext": True,
                "physnet": "physnet1"
            },
            "tenant": objects.Cluster.get_creds(cluster)['tenant']['value'],
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
            "tenant": objects.Cluster.get_creds(cluster)['tenant']['value'],
            "shared": False
        }

    @classmethod
    def generate_predefined_networks(cls, cluster):
        internal_name = cluster.network_config.internal_name
        floating_name = cluster.network_config.floating_name

        return {
            internal_name: cls._generate_internal_network(cluster),
            floating_name: cls.generate_external_network(cluster),
        }

    @classmethod
    def generate_l2(cls, cluster):
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
        if cluster.network_config.segmentation_type in \
                (consts.NEUTRON_SEGMENT_TYPES.gre,
                 consts.NEUTRON_SEGMENT_TYPES.tun):
            res["tunnel_id_ranges"] = utils.join_range(
                cluster.network_config.gre_id_range)
        elif cluster.network_config.segmentation_type == \
                consts.NEUTRON_SEGMENT_TYPES.vlan:
            res["phys_nets"]["physnet2"] = {
                "bridge": "br-prv",
                "vlan_range": utils.join_range(
                    cluster.network_config.vlan_range)
            }

        # Set non-default ml2 configurations
        attrs = objects.Cluster.get_editable_attributes(cluster)
        if 'neutron_mellanox' in attrs and \
                attrs['neutron_mellanox']['plugin']['value'] == 'ethernet':
            res['mechanism_drivers'] = 'mlnx,openvswitch'
            seg_type = cluster.network_config.segmentation_type
            res['tenant_network_types'] = seg_type
            res['type_drivers'] = '{0},flat,local'.format(seg_type)

        return res

    @classmethod
    def generate_l3(cls, cluster):
        l3 = {
            "use_namespaces": True
        }
        attrs = objects.Cluster.get_editable_attributes(cluster)
        if 'nsx_plugin' in attrs and \
                attrs['nsx_plugin']['metadata']['enabled']:
            dhcp_attrs = l3.setdefault('dhcp_agent', {})
            dhcp_attrs['enable_isolated_metadata'] = True
            dhcp_attrs['enable_metadata_network'] = True

        return l3


class NeutronNetworkDeploymentSerializer51(
    NeutronNetworkDeploymentSerializer
):

    @classmethod
    def generate_external_network(cls, cluster):
        ext_netw = super(
            NeutronNetworkDeploymentSerializer51, cls
        ).generate_external_network(cluster)
        ext_netw["L2"] = {
            "network_type": "local",
            "segment_id": None,
            "router_ext": True,
            "physnet": None
        }
        return ext_netw

    @classmethod
    def generate_l2(cls, cluster):
        l2 = super(NeutronNetworkDeploymentSerializer51, cls).\
            generate_l2(cluster)
        l2["phys_nets"].pop("physnet1")
        return l2


class NeutronNetworkDeploymentSerializer60(
    NeutronNetworkDeploymentSerializer51
):

    @classmethod
    def generate_network_scheme(cls, node, networks):
        attrs = super(NeutronNetworkDeploymentSerializer60, cls). \
            generate_network_scheme(node, networks)

        for item in attrs.get('transformations', ()):
            if 'tags' in item:
                item['vlan_ids'] = item['tags']

        # Include information about all subnets that don't belong to this node.
        # This is used during deployment to configure routes to all other
        # networks in the environment.
        nm = objects.Cluster.get_network_manager(node.cluster)
        other_nets = nm.get_networks_not_on_node(node, networks)

        netgroup_mapping = [
            ('storage', 'br-storage'),
            ('management', 'br-mgmt'),
            ('fuelweb_admin', 'br-fw-admin'),
        ]
        if objects.Node.should_have_public(node):
            netgroup_mapping.append(('public', 'br-ex'))

        for ngname, brname in netgroup_mapping:
            netgroup = nm.get_network_by_netname(ngname, networks)
            if netgroup.get('gateway'):
                attrs['endpoints'][brname]['gateway'] = netgroup['gateway']
            attrs['endpoints'][brname]['other_nets'] = \
                other_nets.get(ngname, [])

        if objects.Node.should_have_public(node):
            attrs['endpoints']['br-ex']['default_gateway'] = True
        else:
            gw = nm.get_default_gateway(node.id)
            attrs['endpoints']['br-fw-admin']['gateway'] = gw
            attrs['endpoints']['br-fw-admin']['default_gateway'] = True

        return attrs


class NeutronNetworkDeploymentSerializer61(
    NeutronNetworkDeploymentSerializer60
):

    @classmethod
    def subiface_name(cls, iface_name, net_descr):
        if not net_descr['vlan_id']:
            return iface_name
        else:
            return "{0}.{1}".format(iface_name, net_descr['vlan_id'])

    @classmethod
    def generate_routes(cls, node, attrs, nm, netgroup_mapping, netgroups,
                        networks):
        """Generate static routes for environment with multiple node groups.

        Generate static routes for all networks in all node groups where
        gateway is set.
        :param node: Node instance
        :param attrs: deployment attributes hash (is modified in method)
        :param nm: Network Manager for current environment
        :param netgroup_mapping: endpoint to network name mapping
        :param netgroups: hash of network parameters hashes for node
        :param networks: sequence of network parameters hashes
        :return: None (attrs is modified)
        """
        other_nets = nm.get_networks_not_on_node(node, networks)

        for ngname, brname in netgroup_mapping:
            netgroup = netgroups[ngname]
            if netgroup.get('gateway'):
                via = netgroup['gateway']
                attrs['endpoints'][brname]['routes'] = []
                for cidr in other_nets.get(ngname, []):
                    attrs['endpoints'][brname]['routes'].append({
                        'net': cidr,
                        'via': via
                    })

    @classmethod
    def generate_transformations(cls, node, nm, nets_by_ifaces, is_public,
                                 prv_base_ep):
        transformations = []

        iface_types = consts.NETWORK_INTERFACE_TYPES
        brnames = ['br-fw-admin', 'br-mgmt', 'br-storage']
        if is_public:
            brnames.append('br-ex')

        # Add bridges for networks.
        for brname in brnames:
            transformations.append(cls.add_bridge(brname))

        if is_public:
            # br-floating is an OVS bridge and it's always connected with br-ex
            transformations.append(
                cls.add_bridge('br-floating', provider='ovs'))
            transformations.append(cls.add_patch(
                bridges=['br-floating', 'br-ex'],
                provider='ovs',
                mtu=65000))

        # Dance around Neutron segmentation type.
        if node.cluster.network_config.segmentation_type == \
                consts.NEUTRON_SEGMENT_TYPES.vlan:
            transformations.append(
                cls.add_bridge('br-prv', provider='ovs'))

            if not prv_base_ep:
                prv_base_ep = 'br-aux'
                transformations.append(cls.add_bridge(prv_base_ep))

            transformations.append(cls.add_patch(
                bridges=['br-prv', prv_base_ep],
                provider='ovs',
                mtu=65000))

        elif node.cluster.network_config.segmentation_type in \
                (consts.NEUTRON_SEGMENT_TYPES.gre,
                 consts.NEUTRON_SEGMENT_TYPES.tun):
            transformations.append(
                cls.add_bridge('br-mesh'))

        # Add ports and bonds.
        for iface in node.interfaces:
            if iface.type == iface_types.ether:
                # Add ports for all networks on every unbonded NIC.
                if not iface.bond and iface.name in nets_by_ifaces:
                    tagged = []
                    for net in nets_by_ifaces[iface.name]:
                        # Interface must go prior to subinterfaces.
                        sub_iface = cls.subiface_name(iface.name, net)
                        if not net['vlan_id']:
                            transformations.append(cls.add_port(
                                sub_iface, net['br_name']))
                        else:
                            tagged.append(cls.add_port(
                                sub_iface, net['br_name']))
                    transformations.extend(tagged)
            elif iface.type == iface_types.bond:
                # Add bonds and connect untagged networks' bridges to them.
                # There can be no more than one untagged network on each bond.
                bond_params = {
                    'bond_properties': nm.get_lnx_bond_properties(iface),
                    'interface_properties': nm.get_iface_properties(iface)
                }
                bond_ports = []
                if iface.name in nets_by_ifaces:
                    for net in nets_by_ifaces[iface.name]:
                        if net['vlan_id']:
                            bond_ports.append(cls.add_port(
                                cls.subiface_name(iface.name, net),
                                net['br_name']))
                        else:
                            bond_params['bridge'] = net['br_name']
                transformations.append(cls.add_bond(iface, bond_params))
                transformations.extend(bond_ports)

        return transformations

    @classmethod
    def generate_network_scheme(cls, node, networks):

        # Create a data structure and fill it with static values.
        attrs = {
            'version': '1.1',
            'provider': 'lnx',
            'interfaces': {},  # It's a list of physical interfaces.
            'endpoints': {},
            'roles': {
                'management': 'br-mgmt',
                'storage': 'br-storage',
                'fw-admin': 'br-fw-admin',
            },
        }

        is_public = objects.Node.should_have_public(node)
        if is_public:
            attrs['endpoints']['br-ex'] = {'IP': 'none'}
            attrs['endpoints']['br-floating'] = {'IP': 'none'}
            attrs['roles']['ex'] = 'br-ex'
            attrs['roles']['neutron/floating'] = 'br-floating'

        nm = objects.Cluster.get_network_manager(node.cluster)

        # Populate IP and GW information to endpoints.
        netgroup_mapping = [
            ('storage', 'br-storage'),
            ('management', 'br-mgmt'),
            ('fuelweb_admin', 'br-fw-admin'),
        ]
        if is_public:
            netgroup_mapping.append(('public', 'br-ex'))

        if node.cluster.network_config.segmentation_type in \
                (consts.NEUTRON_SEGMENT_TYPES.gre,
                 consts.NEUTRON_SEGMENT_TYPES.tun):
            netgroup_mapping.append(('private', 'br-mesh'))
            attrs['endpoints']['br-mesh'] = {}
            attrs['roles']['neutron/mesh'] = 'br-mesh'

        netgroups = {}
        nets_by_ifaces = defaultdict(list)
        for ngname, brname in netgroup_mapping:
            # Here we get a dict with network description for this particular
            # node with its assigned IPs and device names for each network.
            netgroup = nm.get_network_by_netname(ngname, networks)
            if netgroup.get('ip'):
                attrs['endpoints'][brname] = {'IP': [netgroup['ip']]}
            netgroups[ngname] = netgroup
            nets_by_ifaces[netgroup['dev']].append({
                'br_name': brname,
                'vlan_id': netgroup['vlan']
            })

        # Add gateway.
        if is_public and netgroups['public'].get('gateway'):
            attrs['endpoints']['br-ex']['gateway'] = \
                netgroups['public']['gateway']
        else:
            gw = nm.get_default_gateway(node.id)
            attrs['endpoints']['br-fw-admin']['gateway'] = gw

        # Fill up interfaces.
        for iface in node.nic_interfaces:
            if iface.bond:
                attrs['interfaces'][iface.name] = {}
            else:
                attrs['interfaces'][iface.name] = \
                    nm.get_iface_properties(iface)

        # Dance around Neutron segmentation type.
        prv_base_ep = None
        if node.cluster.network_config.segmentation_type == \
                consts.NEUTRON_SEGMENT_TYPES.vlan:
            attrs['endpoints']['br-prv'] = {'IP': 'none'}
            attrs['roles']['neutron/private'] = 'br-prv'

            netgroup = nm.get_network_by_netname('private', networks)
            # create br-aux if there is no untagged network (endpoint) on the
            # same interface.
            if netgroup['dev'] in nets_by_ifaces:
                for ep in nets_by_ifaces[netgroup['dev']]:
                    if not ep['vlan_id']:
                        prv_base_ep = ep['br_name']
            if not prv_base_ep:
                nets_by_ifaces[netgroup['dev']].append({
                    'br_name': 'br-aux',
                    'vlan_id': None
                })

        attrs['transformations'] = cls.generate_transformations(
            node, nm, nets_by_ifaces, is_public, prv_base_ep)

        if objects.NodeGroupCollection.get_by_cluster_id(
                node.cluster.id).count() > 1:
            cls.generate_routes(node, attrs, nm, netgroup_mapping, netgroups,
                                networks)

        attrs = cls.generate_driver_information(node, attrs, nm, networks)

        return attrs

    @classmethod
    def generate_driver_information(cls, node, network_scheme, nm, networks):

        network_mapping = network_scheme.get('roles', {})
        endpoints = network_scheme.get('endpoints', {})
        bonds_map = dict((b.name, b) for b in node.bond_interfaces)
        net_name_mapping = {'ex': 'public'}
        managed_networks = ['public', 'storage', 'management', 'private']

        # Add interfaces drivers data
        for iface in node.nic_interfaces:
            if iface.driver or iface.bus_info:
                iface_dict = network_scheme['interfaces'][iface.name]
                if 'vendor_specific' not in iface_dict:
                    iface_dict['vendor_specific'] = {}
                if iface.driver:
                    iface_dict['vendor_specific']['driver'] = iface.driver
                if iface.bus_info:
                    iface_dict['vendor_specific']['bus_info'] = iface.bus_info

        # Add physical allocation data
        for ngname, brname in six.iteritems(network_mapping):
            if ngname in net_name_mapping:
                ngname = net_name_mapping[ngname]
            if ngname not in managed_networks:
                continue
            if 'vendor_specific' not in endpoints[brname]:
                endpoints[brname]['vendor_specific'] = {}
            netgroup = nm.get_network_by_netname(ngname, networks)
            ep_dict = endpoints[brname]['vendor_specific']
            ep_dict['phy_interfaces'] = \
                cls.get_phy_interfaces(bonds_map, netgroup)
            if netgroup['vlan'] > 1:
                ep_dict['vlans'] = netgroup['vlan']

        if node.cluster.network_config.segmentation_type == \
                consts.NEUTRON_SEGMENT_TYPES.vlan:
            private_ep = endpoints[network_mapping['neutron/private']]
            netgroup = nm.get_network_by_netname('private', networks)
            phys = cls.get_phy_interfaces(bonds_map, netgroup)
            if 'vendor_specific' not in private_ep:
                private_ep['vendor_specific'] = {}
            private_ep['vendor_specific']['phy_interfaces'] = phys
            private_ep['vendor_specific']['vlans'] = utils.join_range(
                node.cluster.network_config.vlan_range)

        return network_scheme

    @classmethod
    def get_phy_interfaces(cls, bonds_map, netgroup):
        if netgroup['dev'] in bonds_map.keys():
            phys = [s['name'] for s in bonds_map[netgroup['dev']].slaves]
        else:
            phys = [netgroup['dev']]
        return phys


class NeutronNetworkDeploymentSerializer70(
    NeutronNetworkDeploymentSerializer61
):
    RE_BRIDGE_NAME = re.compile('^br-[0-9a-z\-]{0,11}[0-9a-z]$')

    @classmethod
    def get_node_non_default_networks(cls, node):
        """Returns list of non-default networks assigned to node."""
        nm = objects.Cluster.get_network_manager(node.cluster)
        return filter(lambda net: net['name'] not in consts.NETWORKS,
                      nm.get_node_networks(node))

    @classmethod
    def get_bridge_name(cls, name, suffix=0):
        """Generates linux bridge name based on network name and suffix."""
        if not name.startswith('br-'):
            name = 'br-' + name
        if suffix:
            return (name[0:consts.BRIDGE_NAME_MAX_LEN][:-len(str(suffix))] +
                    str(suffix))
        else:
            return name[0:consts.BRIDGE_NAME_MAX_LEN]

    @classmethod
    def is_valid_non_default_bridge_name(cls, name):
        """Validate bridge name for non-default network."""
        if name in consts.DEFAULT_BRIDGES_NAMES:
            return False
        return bool(cls.RE_BRIDGE_NAME.match(name))

    @classmethod
    def get_node_non_default_bridge_mapping(cls, node):
        """Non-default networks assigned to node with generated bridges names

        Returns dict
        """
        mapping = {}
        for net in cls.get_node_non_default_networks(node):
            brname = cls.get_bridge_name(net['name'])
            suffix = 1
            while (brname in mapping.values() or
                   not cls.is_valid_non_default_bridge_name(brname)):
                brname = cls.get_bridge_name(net['name'], suffix)
                suffix += 1
            mapping[net['name']] = brname
        return mapping

    @classmethod
    def get_network_to_endpoint_mapping(cls, node):
        mapping = {
            consts.NETWORKS.fuelweb_admin: 'br-fw-admin',
            consts.NETWORKS.storage: 'br-storage',
            consts.NETWORKS.management: 'br-mgmt'}

        # roles can be assigned to br-ex only in case it has a public IP
        if objects.Node.should_have_public_with_ip(node):
            mapping[consts.NETWORKS.public] = 'br-ex'

        if node.cluster.network_config.segmentation_type in \
                (consts.NEUTRON_SEGMENT_TYPES.gre,
                 consts.NEUTRON_SEGMENT_TYPES.tun):
            mapping[consts.NETWORKS.private] = 'br-mesh'

        mapping.update(cls.get_node_non_default_bridge_mapping(node))
        return mapping

    @classmethod
    def get_network_to_ip_mapping(cls, node):
        nm = objects.Cluster.get_network_manager(node.cluster)

        mapping = dict()
        networks = nm.get_node_networks(node)
        for net in cls.get_network_to_endpoint_mapping(node):
            netgroup = nm.get_network_by_netname(net, networks)
            if netgroup.get('ip'):
                mapping[net] = netgroup['ip'].split('/')[0]

        return mapping

    @classmethod
    def _get_network_role_mapping(cls, node, mapping):
        """Aggregates common logic for mapping retrieval methods

        these methods are:
        - 'get_network_role_mapping_to_ip'
        - 'get_network_role_mapping_to_interfaces'.
        """
        roles = dict()
        for role in objects.Cluster.get_network_roles(node.cluster):
            default_mapping = mapping.get(role['default_mapping'])
            if default_mapping:
                roles[role['id']] = default_mapping

        return roles

    @classmethod
    def get_network_role_mapping_to_interfaces(cls, node):
        """Returns network roles mapping to interfaces.

        :param node: instance of db.sqlalchemy.models.node.Node
        :return: dict of network roles mapping
        """
        mapping = cls.get_network_to_endpoint_mapping(node)
        return cls._get_network_role_mapping(node, mapping)

    @classmethod
    def get_network_role_mapping_to_ip(cls, node):
        """Returns network roles mapping to IP addresses.

        :param node: instance of db.sqlalchemy.models.node.Node
        :return: dict of network roles mapping
        """
        mapping = cls.get_network_to_ip_mapping(node)
        roles = cls._get_network_role_mapping(node, mapping)
        roles['neutron/floating'] = None
        roles['neutron/private'] = None
        return roles

    @classmethod
    def generate_transformations(cls, node, nm, nets_by_ifaces, is_public,
                                 prv_base_ep):
        transformations = (super(NeutronNetworkDeploymentSerializer70, cls)
                           .generate_transformations(node, nm, nets_by_ifaces,
                                                     is_public, prv_base_ep))
        for brname in six.itervalues(cls.get_node_non_default_bridge_mapping(
                                     node)):
            transformations.insert(0, cls.add_bridge(brname))
        return transformations

    @classmethod
    def generate_vendor_specific_for_endpoint(cls, netgroup):
        return {}

    @classmethod
    def generate_network_scheme(cls, node, networks):
        """Create a data structure and fill it with static values.

        :param node: instance of db.sqlalchemy.models.node.Node
        :param networks: list of networks data dicts
        :return: dict of network scheme attributes
        """
        attrs = {
            'version': '1.1',
            'provider': 'lnx',
            'interfaces': {},
            'endpoints': {},
            'roles': cls.get_network_role_mapping_to_interfaces(node),
        }

        is_public = objects.Node.should_have_public(node)
        if is_public:
            attrs['endpoints']['br-ex'] = {'IP': 'none'}
            attrs['endpoints']['br-floating'] = {'IP': 'none'}
            attrs['roles']['ex'] = 'br-ex'
            attrs['roles']['neutron/floating'] = 'br-floating'

        nm = objects.Cluster.get_network_manager(node.cluster)

        # Populate IP and GW information to endpoints.
        netgroup_mapping = (cls.get_network_to_endpoint_mapping(node)
                            .items())
        # get_network_to_endpoint_mapping() adds mapping for 'public' only in
        # case the node 'should_have_public_with_ip'. Here we need to add it
        # because proper transformations should be formed no matter if br-ex
        # has IP or not.
        public_mapping = (consts.NETWORKS.public, 'br-ex')
        if is_public and public_mapping not in netgroup_mapping:
            netgroup_mapping.append(public_mapping)

        if node.cluster.network_config.segmentation_type in \
                (consts.NEUTRON_SEGMENT_TYPES.gre,
                 consts.NEUTRON_SEGMENT_TYPES.tun):
            attrs['endpoints']['br-mesh'] = {}
            attrs['roles']['neutron/mesh'] = 'br-mesh'

        netgroups = {}
        nets_by_ifaces = defaultdict(list)
        for ngname, brname in netgroup_mapping:
            # Here we get a dict with network description for this particular
            # node with its assigned IPs and device names for each network.
            netgroup = nm.get_network_by_netname(ngname, networks)
            if netgroup.get('ip'):
                attrs['endpoints'][brname] = {'IP': [netgroup['ip']]}
                vs = cls.generate_vendor_specific_for_endpoint(netgroup)
                if bool(vs):
                    attrs['endpoints'][brname]['vendor_specific'] = vs
            netgroups[ngname] = netgroup
            nets_by_ifaces[netgroup['dev']].append({
                'br_name': brname,
                'vlan_id': netgroup['vlan']
            })

        # Add gateway.
        if objects.Node.should_have_public_with_ip(node):
            attrs['endpoints']['br-ex']['gateway'] = \
                netgroups['public']['gateway']
        else:
            gw = nm.get_default_gateway(node.id)
            attrs['endpoints']['br-fw-admin']['gateway'] = gw

        # Fill up interfaces.
        for iface in node.nic_interfaces:
            if iface.bond:
                attrs['interfaces'][iface.name] = {}
            else:
                attrs['interfaces'][iface.name] = \
                    nm.get_iface_properties(iface)

        # Dance around Neutron segmentation type.
        prv_base_ep = None
        if node.cluster.network_config.segmentation_type == \
                consts.NEUTRON_SEGMENT_TYPES.vlan:
            attrs['endpoints']['br-prv'] = {'IP': 'none'}
            attrs['roles']['neutron/private'] = 'br-prv'

            netgroup = nm.get_network_by_netname('private', networks)
            # create br-aux if there is no untagged network (endpoint) on the
            # same interface.
            if netgroup['dev'] in nets_by_ifaces:
                for ep in nets_by_ifaces[netgroup['dev']]:
                    if not ep['vlan_id']:
                        prv_base_ep = ep['br_name']
            if not prv_base_ep:
                nets_by_ifaces[netgroup['dev']].append({
                    'br_name': 'br-aux',
                    'vlan_id': None
                })

        attrs['transformations'] = cls.generate_transformations(
            node, nm, nets_by_ifaces, is_public, prv_base_ep)

        if objects.NodeGroupCollection.get_by_cluster_id(
                node.cluster.id).count() > 1:
            cls.generate_routes(node, attrs, nm, netgroup_mapping, netgroups,
                                networks)

        attrs = cls.generate_driver_information(node, attrs, nm, networks)

        if node.cluster.network_config.segmentation_type in \
                (consts.NEUTRON_SEGMENT_TYPES.gre,
                 consts.NEUTRON_SEGMENT_TYPES.tun):
            attrs['roles'].pop('neutron/private', None)

        if node.cluster.network_config.segmentation_type == \
                consts.NEUTRON_SEGMENT_TYPES.vlan:
            attrs['roles'].pop('neutron/mesh', None)

        return attrs

    @classmethod
    def generate_driver_information(cls, node, network_scheme, nm, networks):
        # Add interfaces drivers data
        for iface in node.nic_interfaces:
            if iface.driver or iface.bus_info:
                iface_dict = network_scheme['interfaces'][iface.name]
                if 'vendor_specific' not in iface_dict:
                    iface_dict['vendor_specific'] = {}
                if iface.driver:
                    iface_dict['vendor_specific']['driver'] = iface.driver
                if iface.bus_info:
                    iface_dict['vendor_specific']['bus_info'] = iface.bus_info

        return network_scheme

    @classmethod
    def generate_network_metadata(cls, cluster):
        nodes = dict()
        nm = objects.Cluster.get_network_manager(cluster)

        for node in objects.Cluster.get_nodes_not_for_deletion(cluster):
            name = objects.Node.get_slave_name(node)
            node_roles = objects.Node.all_roles(node)
            network_roles = cls.get_network_role_mapping_to_ip(node)

            nodes[name] = {
                "uid": node.uid,
                "fqdn": objects.Node.get_node_fqdn(node),
                "name": name,
                "user_node_name": node.name,
                "swift_zone": node.uid,
                "node_roles": node_roles,
                "network_roles": network_roles
            }

        return dict(
            nodes=nodes,
            vips=nm.assign_vips_for_net_groups(cluster)
        )

    @classmethod
    def get_common_attrs(cls, cluster, attrs):
        node_attrs = super(NeutronNetworkDeploymentSerializer70,
                           cls).get_common_attrs(cluster, attrs)
        node_attrs['network_metadata'] = cls.generate_network_metadata(cluster)
        return node_attrs


class NeutronNetworkTemplateSerializer70(
    NeutronNetworkDeploymentSerializer70
):

    @classmethod
    def _get_network_roles(cls, node):
        """Returns network roles for the node based on the assigned roles."""
        roles = {}
        template = node.network_template
        for node_role in node.all_roles:
            role_templates = template['templates_for_node_role'][node_role]
            for role_template in role_templates:
                for role, ep in (template['templates'][role_template]
                                 ['roles'].items()):
                    roles[role] = ep

        return roles

    @classmethod
    def generate_transformations(cls, node, *args):
        """Overrides default transformation generation

        Transformations are taken verbatim from each role template's
        transformations section.
        """
        txs = []
        role_templates = OrderedDict()
        template = node.network_template

        roles = sorted(node.all_roles)

        # We need a unique, ordered list of all role templates that
        # apply to this node. The keys of an OrderedDict act as an
        # ordered set. The order of transformations is important which
        # is why we can't just use a set. The list needs to be unique
        # because duplicated transformations will break deployment.
        # If some template contains 'priority' property, than node's
        # templates order should be based on it, in other case, all node's
        # templates will have zero priority and have the same order as
        # there is no property field.
        for role in roles:
            for t in template['templates_for_node_role'][role]:
                role_templates[t] = template['templates'][t].get(
                    'priority', 0)

        # sort network schemes by priority
        sorted_role_templates = sorted(role_templates.iteritems(),
                                       key=lambda x: x[1])

        for t, p in sorted_role_templates:
            txs.extend(template['templates'][t]['transformations'])

        return txs

    def generate_vendor_specific_for_endpoint(cls, netgroup):
        return {}

    @classmethod
    def generate_network_scheme(cls, node, networks):

        roles = cls._get_network_roles(node)
        # Create a data structure and fill it with static values.
        attrs = {
            'version': '1.1',
            'provider': 'lnx',
            'interfaces': {},  # It's a list of physical interfaces.
            'endpoints': {},
            'roles': roles,
        }

        nm = objects.Cluster.get_network_manager(node.cluster)

        netgroups = nm.get_node_networks_with_ips(node)
        netgroup_mapping = nm.get_node_network_mapping(node)
        for ngname, brname in netgroup_mapping:
            netgroup = netgroups.get(ngname, {})
            ip_addr = netgroup.get('ip')
            if ip_addr:
                attrs['endpoints'][brname] = {'IP': [ip_addr]}
                vs = cls.generate_vendor_specific_for_endpoint(netgroup)
                if bool(vs):
                    attrs['endpoints'][brname]['vendor_specific'] = vs
            else:
                attrs['endpoints'][brname] = {'IP': 'none'}

        # TODO(rmoe): fix gateway selection
        if 'public/vip' in roles:
            public_ep = roles['public/vip']
            public_net = None

            for network_group, endpoint in netgroup_mapping:
                if endpoint == public_ep:
                    public_net = network_group
                    break

            attrs['endpoints'][public_ep]['gateway'] = \
                netgroups[public_net]['gateway']

            # This can go away when we allow separate public and floating nets
            floating_ep = roles['neutron/floating']
            if floating_ep not in attrs['endpoints']:
                attrs['endpoints'][floating_ep] = {'IP': 'none'}
        else:
            admin_ep = roles['admin/pxe']
            attrs['endpoints'][admin_ep]['gateway'] = \
                nm.get_default_gateway(node.id)

        # Fill up interfaces.
        for iface in node.nic_interfaces:
            if iface.bond:
                attrs['interfaces'][iface.name] = {}
            else:
                attrs['interfaces'][iface.name] = \
                    nm.get_iface_properties(iface)

        attrs['transformations'] = cls.generate_transformations(node)

        if objects.NodeGroupCollection.get_by_cluster_id(
                node.cluster.id).count() > 1:
            cls.generate_routes(node, attrs, nm, netgroup_mapping, netgroups,
                                networks)

        attrs = cls.generate_driver_information(node, attrs, nm, networks)

        return attrs

    @classmethod
    def _get_endpoint_to_ip_mapping(cls, node):
        nm = objects.Cluster.get_network_manager(node.cluster)
        net_to_ips = nm.get_node_networks_with_ips(node)

        mapping = dict()
        net_to_ep = nm.get_node_network_mapping(node)
        for network, ep in net_to_ep:
            netgroup = net_to_ips.get(network, {})
            if netgroup.get('ip'):
                mapping[ep] = netgroup['ip'].split('/')[0]

        return mapping

    @classmethod
    def get_network_role_mapping_to_ip(cls, node):
        """Returns network roles mapping to IP addresses for templates.

        :param node: instance of db.sqlalchemy.models.node.Node
        :return: dict of network roles mapping
        """
        network_roles = cls._get_network_roles(node)
        ip_per_ep = cls._get_endpoint_to_ip_mapping(node)
        roles = {}
        for role, ep in network_roles.items():
            roles[role] = ip_per_ep.get(ep)
        return roles

    @classmethod
    def update_nodes_net_info(cls, cluster, nodes):
        """Adds information about networks to each node.

        This info is deprecated in 7.0 and should be removed in later version.
        """
        nm = objects.Cluster.get_network_manager(cluster)
        for node in objects.Cluster.get_nodes_not_for_deletion(cluster):
            netw_data = []
            for name, data in six.iteritems(
                    nm.get_node_networks_with_ips(node)):
                data['name'] = name
                netw_data.append(data)
            addresses = {}
            for net in netw_data:
                render_addr_mask = net['meta'].get('render_addr_mask')
                if render_addr_mask:
                    addresses.update(cls.get_addr_mask(
                        netw_data,
                        net['name'],
                        render_addr_mask))
            [n.update(addresses) for n in nodes
             if n['uid'] == str(node.uid)]
        return nodes


class GenerateL23Mixin80(object):
    @classmethod
    def generate_l2(cls, cluster):
        l2 = super(GenerateL23Mixin80, cls).generate_l2(cluster)
        l2["phys_nets"]["physnet1"] = {
            "bridge": consts.DEFAULT_BRIDGES_NAMES.br_floating,
            "vlan_range": None
        }
        if objects.Cluster.is_component_enabled(cluster, 'ironic'):
            l2["phys_nets"]["physnet-ironic"] = {
                "bridge": consts.DEFAULT_BRIDGES_NAMES.br_ironic,
                "vlan_range": None
            }
        return l2

    @classmethod
    def generate_external_network(cls, cluster):
        ext_net = super(GenerateL23Mixin80, cls).generate_external_network(
            cluster
        )
        ext_net["L2"] = {
            "network_type": "flat",
            "segment_id": None,
            "router_ext": True,
            "physnet": "physnet1"
        }
        return ext_net

    @classmethod
    def _generate_baremetal_network(cls, cluster):
        ng = objects.NetworkGroup.get_from_node_group_by_name(
            objects.Cluster.get_default_group(cluster).id, 'baremetal')
        return {
            "L3": {
                "subnet": ng.cidr,
                "nameservers": cluster.network_config.dns_nameservers,
                "gateway": cluster.network_config.baremetal_gateway,
                "floating": utils.join_range(
                    cluster.network_config.baremetal_range),
                "enable_dhcp": True
            },
            "L2": {
                "network_type": "flat",
                "segment_id": None,
                "router_ext": False,
                "physnet": "physnet-ironic"
            },
            "tenant": objects.Cluster.get_creds(
                cluster)['tenant']['value'],
            "shared": True
        }

    @classmethod
    def generate_predefined_networks(cls, cluster):
        nets = super(GenerateL23Mixin80, cls).generate_predefined_networks(
            cluster
        )
        if objects.Cluster.is_component_enabled(cluster, 'ironic'):
            nets["baremetal"] = cls._generate_baremetal_network(cluster)
        return nets


class NeutronNetworkDeploymentSerializer80(
    GenerateL23Mixin80,
    NeutronNetworkDeploymentSerializer70
):

    @classmethod
    def render_floating_ranges(cls, floating_ranges):
        return [utils.join_range(x) for x in floating_ranges]

    @classmethod
    def get_network_to_endpoint_mapping(cls, node):
        mapping = {
            consts.NETWORKS.fuelweb_admin:
                consts.DEFAULT_BRIDGES_NAMES.br_fw_admin,
            consts.NETWORKS.storage:
                consts.DEFAULT_BRIDGES_NAMES.br_storage,
            consts.NETWORKS.management:
                consts.DEFAULT_BRIDGES_NAMES.br_mgmt}
        # roles can be assigned to br-ex only in case it has a public IP
        if objects.Node.should_have_public_with_ip(node):
            mapping[consts.NETWORKS.public] = \
                consts.DEFAULT_BRIDGES_NAMES.br_ex
        if node.cluster.network_config.segmentation_type in \
                (consts.NEUTRON_SEGMENT_TYPES.gre,
                 consts.NEUTRON_SEGMENT_TYPES.tun):
            mapping[consts.NETWORKS.private] = \
                consts.DEFAULT_BRIDGES_NAMES.br_mesh
        if objects.Cluster.is_component_enabled(node.cluster, 'ironic'):
            mapping[consts.NETWORKS.baremetal] = \
                consts.DEFAULT_BRIDGES_NAMES.br_baremetal
        mapping.update(cls.get_node_non_default_bridge_mapping(node))
        return mapping

    @classmethod
    def generate_transformations(cls, node, nm, nets_by_ifaces, is_public,
                                 prv_base_ep):
        transformations = (super(NeutronNetworkDeploymentSerializer80, cls)
                           .generate_transformations(node, nm, nets_by_ifaces,
                                                     is_public, prv_base_ep))
        if objects.Cluster.is_component_enabled(node.cluster, 'ironic'):
            transformations.insert(0, cls.add_bridge(
                consts.DEFAULT_BRIDGES_NAMES.br_baremetal))
            transformations.append(cls.add_bridge(
                consts.DEFAULT_BRIDGES_NAMES.br_ironic, provider='ovs'))
            transformations.append(cls.add_patch(
                bridges=[consts.DEFAULT_BRIDGES_NAMES.br_ironic,
                         consts.DEFAULT_BRIDGES_NAMES.br_baremetal],
                provider='ovs'))
        return transformations

    @classmethod
    def generate_routes(cls, node, attrs, nm, netgroup_mapping, netgroups,
                        networks):
        """Generate static routes for environment with multiple node groups.

        Generate static routes for all networks in all node groups where
        gateway is set. Routes are not generated between shared L3 segments.
        :param node: Node instance
        :param attrs: deployment attributes hash (is modified in method)
        :param nm: Network Manager for current environment
        :param netgroup_mapping: endpoint to network name mapping
        :param netgroups: hash of network parameters hashes for node
        :param networks: sequence of network parameters hashes
        :return: None (attrs is modified)
        """
        other_nets = nm.get_networks_not_on_node(node, networks)
        cidrs_in_use = set(ng['cidr'] for ng in netgroups if 'cidr' in ng)

        for ngname, brname in netgroup_mapping:
            netgroup = netgroups[ngname]
            if netgroup.get('gateway') and netgroup.get('cidr'):
                via = netgroup['gateway']
                attrs['endpoints'][brname]['routes'] = []
                for cidr in other_nets.get(ngname, []):
                    if cidr not in cidrs_in_use:
                        attrs['endpoints'][brname]['routes'].append({
                            'net': cidr,
                            'via': via
                        })
                        cidrs_in_use.add(cidr)


class NeutronNetworkTemplateSerializer80(
    GenerateL23Mixin80,
    NeutronNetworkTemplateSerializer70
):
    pass


class VendorSpecificMixin90(object):
    @classmethod
    def generate_vendor_specific_for_endpoint(cls, netgroup):
        vendor_specific = {}
        if netgroup.get('gateway') and netgroup.get('cidr'):
            vendor_specific['provider_gateway'] = netgroup.get('gateway')
        return vendor_specific


class NeutronNetworkDeploymentSerializer90(
    VendorSpecificMixin90,
    NeutronNetworkDeploymentSerializer80
):
    pass


class NeutronNetworkTemplateSerializer90(
    VendorSpecificMixin90,
    NeutronNetworkTemplateSerializer80
):
    pass
