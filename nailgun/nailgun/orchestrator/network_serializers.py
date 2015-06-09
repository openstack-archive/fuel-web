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

"""Network deployment serializers for orchestrator"""

from collections import defaultdict
from copy import deepcopy

from netaddr import IPNetwork

import six

from nailgun import objects

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.objects import Cluster
from nailgun.settings import settings
from nailgun import utils


class NetworkDeploymentSerializer(object):

    @classmethod
    def update_nodes_net_info(cls, cluster, nodes):
        """Adds information about networks to each node."""
        for node in objects.Cluster.get_nodes_not_for_deletion(cluster):
            netw_data = node.network_data
            addresses = {}
            for net in node.cluster.network_groups:
                if net.name == 'public' and \
                        not objects.Node.should_have_public(node):
                    continue
                if net.meta.get('render_addr_mask'):
                    addresses.update(cls.get_addr_mask(
                        netw_data,
                        net.name,
                        net.meta.get('render_addr_mask')))
            [n.update(addresses) for n in nodes
                if n['uid'] == str(node.uid)]
        return nodes

    @classmethod
    def get_common_attrs(cls, cluster, attrs):
        """Cluster network attributes."""
        common = cls.network_provider_cluster_attrs(cluster)
        common.update(
            cls.network_ranges(Cluster.get_default_group(cluster).id))
        common.update({'master_ip': settings.MASTER_IP})

        common['nodes'] = deepcopy(attrs['nodes'])
        common['nodes'] = cls.update_nodes_net_info(cluster, common['nodes'])

        return common

    @classmethod
    def get_node_attrs(cls, node):
        """Node network attributes."""
        return cls.network_provider_node_attrs(node.cluster, node)

    @classmethod
    def network_provider_cluster_attrs(cls, cluster):
        raise NotImplementedError()

    @classmethod
    def network_provider_node_attrs(cls, cluster, node):
        raise NotImplementedError()

    @classmethod
    def network_ranges(cls, group_id):
        """Returns ranges for network groups
        except range for public network for each node
        """
        ng_db = db().query(NetworkGroup).filter_by(group_id=group_id).all()
        attrs = {}
        for net in ng_db:
            net_name = net.name + '_network_range'
            if net.meta.get("render_type") == 'ip_ranges':
                attrs[net_name] = cls.get_ip_ranges_first_last(net)
            elif net.meta.get("render_type") == 'cidr' and net.cidr:
                attrs[net_name] = net.cidr
        return attrs

    @classmethod
    def get_ip_ranges_first_last(cls, network_group):
        """Get all ip ranges in "10.0.0.0-10.0.0.255" format
        """
        return [
            "{0}-{1}".format(ip_range.first, ip_range.last)
            for ip_range in network_group.ip_ranges
        ]

    @classmethod
    def get_addr_mask(cls, network_data, net_name, render_name):
        """Get addr for network by name
        """
        nets = filter(
            lambda net: net['name'] == net_name,
            network_data)

        if not nets or 'ip' not in nets[0]:
            raise errors.CanNotFindNetworkForNode(
                'Cannot find network with name: %s' % net_name)

        net = nets[0]['ip']
        return {
            render_name + '_address': str(IPNetwork(net).ip),
            render_name + '_netmask': str(IPNetwork(net).netmask)
        }

    @staticmethod
    def get_admin_ip_w_prefix(node):
        """Getting admin ip and assign prefix from admin network."""
        network_manager = objects.Node.get_network_manager(node)
        admin_ip = network_manager.get_admin_ip_for_node(node.id)
        admin_ip = IPNetwork(admin_ip)

        # Assign prefix from admin network
        admin_net = IPNetwork(
            network_manager.get_admin_network_group(node.id).cidr
        )
        admin_ip.prefixlen = admin_net.prefixlen

        return str(admin_ip)

    @classmethod
    def add_bridge(cls, name, provider=None):
        """Add bridge to schema
        It will take global provider if it is omitted here
        """
        bridge = {
            'action': 'add-br',
            'name': name
        }
        if provider:
            bridge['provider'] = provider
        return bridge

    @classmethod
    def add_port(cls, name, bridge, provider=None):
        """Add port to schema
        Bridge name may be None, port will not be connected to any bridge then
        It will take global provider if it is omitted here
        Port name can be in form "XX" or "XX.YY", where XX - NIC name,
        YY - vlan id. E.g. "eth0", "eth0.1021". This will create corresponding
        interface if name includes vlan id.
        """
        port = {
            'action': 'add-port',
            'name': name
        }
        if bridge:
            port['bridge'] = bridge
        if provider:
            port['provider'] = provider
        return port

    @classmethod
    def add_bond(cls, iface, parameters):
        """Add bond to schema
        All required parameters should be inside parameters dict. (e.g.
        bond_properties, interface_properties, provider, bridge).
        bond_properties is obligatory, others are optional.
        bridge should be set if bridge for untagged network is to be connected
        to bond. Ports are to be created for tagged networks which should be
        connected to bond (e.g. port "bond-X.212" for bridge "br-ex").
        """
        bond = {
            'action': 'add-bond',
            'name': iface.name,
            'interfaces': sorted(x['name'] for x in iface.slaves),
        }
        if iface.interface_properties.get('mtu'):
            bond['mtu'] = iface.interface_properties['mtu']
        if parameters:
            bond.update(parameters)
        return bond

    @classmethod
    def add_patch(cls, bridges, provider=None, mtu=None):
        """Add patch to schema
        Patch connects two bridges listed in 'bridges'.
        OVS bridge must go first in 'bridges'.
        It will take global provider if it is omitted here
        """
        patch = {
            'action': 'add-patch',
            'bridges': bridges,
        }
        if provider:
            patch['provider'] = provider
        if mtu:
            patch['mtu'] = mtu
        return patch


class NovaNetworkDeploymentSerializer(NetworkDeploymentSerializer):

    @classmethod
    def network_provider_cluster_attrs(cls, cluster):
        return {
            'novanetwork_parameters': cls.novanetwork_attrs(cluster),
            'dns_nameservers': cluster.network_config.dns_nameservers,
            'fixed_network_range': cluster.network_config.fixed_networks_cidr,
            'floating_network_range': [
                "{0}-{1}".format(ip_range[0], ip_range[1])
                for ip_range in cluster.network_config.floating_ranges
            ]
        }

    @classmethod
    def network_provider_node_attrs(cls, cluster, node):
        network_data = node.network_data
        interfaces = cls.configure_interfaces(node)
        cls.__add_hw_interfaces(interfaces, node.meta['interfaces'])

        # Interfaces assignment
        attrs = {'network_data': interfaces}
        attrs.update(cls.interfaces_list(network_data))

        if cluster.network_config.net_manager == 'VlanManager':
            attrs.update(cls.add_vlan_interfaces(node))

        return attrs

    @classmethod
    def novanetwork_attrs(cls, cluster):
        """Network configuration
        """
        attrs = {'network_manager': cluster.network_config.net_manager}

        # network_size is required for all managers, otherwise
        # puppet will use default (255)
        if attrs['network_manager'] == consts.NOVA_NET_MANAGERS.VlanManager:
            attrs['num_networks'] = \
                cluster.network_config.fixed_networks_amount
            attrs['vlan_start'] = \
                cluster.network_config.fixed_networks_vlan_start
            attrs['network_size'] = cluster.network_config.fixed_network_size
        elif (attrs['network_manager'] ==
              consts.NOVA_NET_MANAGERS.FlatDHCPManager):
            # We need set maximum available size for specific mask for FlatDHCP
            # because default 256 caused problem
            net_cidr = IPNetwork(cluster.network_config.fixed_networks_cidr)
            attrs['network_size'] = net_cidr.size
            attrs['num_networks'] = 1

        return attrs

    @classmethod
    def add_vlan_interfaces(cls, node):
        """Assign fixed_interfaces and vlan_interface.
        They should be equal.
        """
        net_manager = objects.Node.get_network_manager(node)
        fixed_interface = net_manager._get_interface_by_network_name(
            node.id, 'fixed')

        attrs = {'fixed_interface': fixed_interface.name,
                 'vlan_interface': fixed_interface.name}
        return attrs

    @classmethod
    def configure_interfaces(cls, node):
        """Configure interfaces
        """
        network_data = node.network_data
        interfaces = {}

        for network in network_data:
            network_name = network['name']
            name = cls.__make_interface_name(network.get('dev'),
                                             network.get('vlan'))

            interfaces.setdefault(name, {'interface': name, 'ipaddr': []})
            interface = interfaces[name]
            if network.get('ip'):
                interface['ipaddr'].append(network.get('ip'))

            if network_name == 'fuelweb_admin':
                admin_ip_addr = cls.get_admin_ip_w_prefix(node)
                interface['ipaddr'].append(admin_ip_addr)
            elif network_name == 'public' and network.get('gateway'):
                interface['gateway'] = network['gateway']
                interface['default_gateway'] = True

        for if_name, if_data in interfaces.iteritems():
            if len(if_data['ipaddr']) == 0:
                if_data['ipaddr'] = 'none'

        interfaces['lo'] = {'interface': 'lo', 'ipaddr': ['127.0.0.1/8']}

        return interfaces

    @classmethod
    def __make_interface_name(cls, name, vlan):
        """Make interface name
        """
        if name and vlan:
            return '.'.join([name, str(vlan)])
        return name

    @classmethod
    def __add_hw_interfaces(cls, interfaces, hw_interfaces):
        """Add interfaces which not represents in
        interfaces list but they are represented on node
        """
        for hw_interface in hw_interfaces:
            if hw_interface['name'] not in interfaces:
                interfaces[hw_interface['name']] = {
                    'interface': hw_interface['name'],
                    'ipaddr': "none"
                }

    @classmethod
    def interfaces_list(cls, network_data):
        """Generate list of interfaces
        """
        interfaces = {}
        for network in network_data:
            if_name = cls.__make_interface_name(
                network.get('dev'),
                network.get('vlan'))
            interfaces['%s_interface' % network['name']] = if_name
            if network['name'] == 'public':
                interfaces['floating_interface'] = if_name
        return interfaces


class NovaNetworkDeploymentSerializer61(
    NovaNetworkDeploymentSerializer
):

    @classmethod
    def network_provider_node_attrs(cls, cluster, node):
        return {'network_scheme': cls.generate_network_scheme(node)}

    @classmethod
    def subiface_name(cls, iface_name, net_descr):
        if not net_descr['vlan_id']:
            return iface_name
        else:
            return "{0}.{1}".format(iface_name, net_descr['vlan_id'])

    @classmethod
    def generate_transformations(cls, node, nm, nets_by_ifaces,
                                 fixed_sub_iface):
        iface_types = consts.NETWORK_INTERFACE_TYPES
        brnames = ['br-fw-admin', 'br-storage', 'br-mgmt', 'br-ex']
        transformations = []

        # add bridges for network roles
        for brname in brnames:
            transformations.append(cls.add_bridge(brname))

        # fill up ports and bonds
        for iface in node.interfaces:
            if iface.type == iface_types.ether:
                # add ports for all networks on every unbonded NIC
                if not iface.bond and iface.name in nets_by_ifaces:
                    tagged = []
                    for net in nets_by_ifaces[iface.name]:
                        sub_iface = cls.subiface_name(iface.name, net)
                        # Interface must go prior to subinterfaces.
                        if not net['vlan_id']:
                            transformations.append(
                                cls.add_port(sub_iface, net['br_name']))
                        else:
                            tagged.append(
                                cls.add_port(sub_iface, net['br_name']))
                        # we should avoid adding the port twice in case of
                        # VlanManager
                        if fixed_sub_iface == sub_iface:
                            fixed_sub_iface = None
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
                # we should avoid adding the port twice in case of
                # VlanManager
                if fixed_sub_iface == iface.name:
                    fixed_sub_iface = None
        # add manager-related ports
        if fixed_sub_iface:
            transformations.append(cls.add_port(fixed_sub_iface, None))
        return transformations

    @classmethod
    def generate_network_scheme(cls, node):

        # create network scheme structure and fill it with static values
        attrs = {
            'version': '1.1',
            'provider': 'lnx',
            'interfaces': {},
            'endpoints': {},
            'roles': {
                'fw-admin': 'br-fw-admin',
                'storage': 'br-storage',
                'management': 'br-mgmt',
                'ex': 'br-ex',
            },
        }

        netgroup_mapping = [
            ('fuelweb_admin', 'br-fw-admin'),
            ('storage', 'br-storage'),
            ('management', 'br-mgmt'),
            ('public', 'br-ex'),
            ('fixed', '')  # will be determined in code below
        ]

        nm = objects.Node.get_network_manager(node)

        # populate IP address information to endpoints
        netgroups = {}
        nets_by_ifaces = defaultdict(list)
        fixed_sub_iface = None
        for ngname, brname in netgroup_mapping:
            # Here we get a dict with network description for this particular
            # node with its assigned IPs and device names for each network.
            netgroup = nm.get_node_network_by_netname(node, ngname)
            if ngname == 'fixed':
                vlan_id = None
                if node.cluster.network_config.net_manager == \
                        consts.NOVA_NET_MANAGERS.FlatDHCPManager:
                    vlan_id = \
                        node.cluster.network_config.fixed_networks_vlan_start
                net = {'vlan_id': vlan_id}
                fixed_sub_iface = cls.subiface_name(netgroup['dev'], net)
                attrs['endpoints'][fixed_sub_iface] = {'IP': 'none'}
            else:
                nets_by_ifaces[netgroup['dev']].append({
                    'br_name': brname,
                    'vlan_id': netgroup['vlan']
                })
                if netgroup.get('ip'):
                    attrs['endpoints'][brname] = {'IP': [netgroup['ip']]}
            netgroups[ngname] = netgroup

        attrs['endpoints']['br-ex']['gateway'] = \
            netgroups['public']['gateway']

        # add manager-related roles
        if node.cluster.network_config.net_manager == \
                consts.NOVA_NET_MANAGERS.VlanManager:
            attrs['roles']['novanetwork/vlan'] = fixed_sub_iface
        else:
            attrs['roles']['novanetwork/fixed'] = fixed_sub_iface

        for iface in node.nic_interfaces:
            if iface.bond:
                attrs['interfaces'][iface.name] = {}
            else:
                attrs['interfaces'][iface.name] = \
                    nm.get_iface_properties(iface)

        attrs['transformations'] = \
            cls.generate_transformations(node, nm, nets_by_ifaces,
                                         fixed_sub_iface)

        return attrs


class NeutronNetworkDeploymentSerializer(NetworkDeploymentSerializer):

    @classmethod
    def network_provider_cluster_attrs(cls, cluster):
        """Cluster attributes."""
        attrs = {'quantum': True,
                 'quantum_settings': cls.neutron_attrs(cluster)}

        if cluster.mode == 'multinode':
            for node in cluster.nodes:
                if cls._node_has_role_by_name(node, 'controller'):
                    net_manager = objects.Node.get_network_manager(node)
                    mgmt_cidr = net_manager.get_node_network_by_netname(
                        node,
                        'management'
                    )['ip']
                    attrs['management_vip'] = mgmt_cidr.split('/')[0]
                    break

        return attrs

    @classmethod
    def network_provider_node_attrs(cls, cluster, node):
        """Serialize node, then it will be
        merged with common attributes
        """
        node_attrs = {'network_scheme': cls.generate_network_scheme(node)}
        node_attrs = cls.mellanox_settings(node_attrs, node)
        return node_attrs

    @classmethod
    def mellanox_settings(cls, node_attrs, node):
        """Serialize mellanox node attrs, then it will be
        merged with common attributes, if mellanox plugin or iSER storage
        enabled.
        """
        # Get Mellanox data
        neutron_mellanox_data =  \
            Cluster.get_attributes(node.cluster).editable\
            .get('neutron_mellanox', {})

        # Get storage data
        storage_data = \
            Cluster.get_attributes(node.cluster).editable.get('storage', {})

        # Get network manager
        nm = objects.Node.get_network_manager(node)

        # Init mellanox dict
        node_attrs['neutron_mellanox'] = {}

        # Find Physical port for VFs generation
        if 'plugin' in neutron_mellanox_data and \
           neutron_mellanox_data['plugin']['value'] == 'ethernet':
            node_attrs = cls.set_mellanox_ml2_config(node_attrs, node, nm)

        # Fix network scheme to have physical port for RDMA if iSER enabled
        if 'iser' in storage_data and storage_data['iser']['value']:
            node_attrs = cls.fix_iser_port(node_attrs, node, nm)

        return node_attrs

    @classmethod
    def set_mellanox_ml2_config(cls, node_attrs, node, nm):
        """Change the yaml file to include the required configurations
        for ml2 mellanox mechanism driver.
        should be called only in case of mellanox SR-IOV plugin usage.
        """
        # Set physical port for SR-IOV virtual functions
        node_attrs['neutron_mellanox']['physical_port'] = \
            nm.get_node_network_by_netname(node, 'private')['dev']

        # Set ML2 eswitch section conf
        ml2_eswitch = {}
        ml2_eswitch['vnic_type'] = 'hostdev'
        ml2_eswitch['apply_profile_patch'] = True
        node_attrs['neutron_mellanox']['ml2_eswitch'] = ml2_eswitch

        return node_attrs

    @classmethod
    def fix_iser_port(cls, node_attrs, node, nm):
        """Change the iser port to eth_iser probed (VF on the HV) interface
        instead of br-storage. that change is made due to RDMA
        (Remote Direct Memory Access) limitation of working with physical
        interfaces.
        """
        # Set a new unique name for iSER virtual port
        iser_new_name = 'eth_iser0'

        # Add iSER extra params to astute.yaml
        node_attrs['neutron_mellanox']['storage_parent'] = \
            nm.get_node_network_by_netname(node, 'storage')['dev']
        node_attrs['neutron_mellanox']['iser_interface_name'] = iser_new_name

        # Get VLAN if exists
        storage_vlan = \
            nm.get_node_network_by_netname(node, 'storage').get('vlan')

        if storage_vlan:
            vlan_name = "vlan{0}".format(storage_vlan)

            # Set storage rule to iSER interface vlan interface
            node_attrs['network_scheme']['roles']['storage'] = vlan_name

            # Set iSER interface vlan interface
            node_attrs['network_scheme']['interfaces'][vlan_name] = \
                {'L2': {'vlan_splinters': 'off'}}
            node_attrs['network_scheme']['endpoints'][vlan_name] = \
                node_attrs['network_scheme']['endpoints'].pop('br-storage', {})
            node_attrs['network_scheme']['endpoints'][vlan_name]['vlandev'] = \
                iser_new_name
        else:

            # Set storage rule to iSER port
            node_attrs['network_scheme']['roles']['storage'] = iser_new_name

            # Set iSER endpoint with br-storage parameters
            node_attrs['network_scheme']['endpoints'][iser_new_name] = \
                node_attrs['network_scheme']['endpoints'].pop('br-storage', {})
            node_attrs['network_scheme']['interfaces'][iser_new_name] = \
                {'L2': {'vlan_splinters': 'off'}}

        return node_attrs

    @classmethod
    def _node_has_role_by_name(cls, node, rolename):
        if rolename in node.pending_roles or rolename in node.roles:
            return True
        return False

    @classmethod
    def neutron_attrs(cls, cluster):
        """Network configuration for Neutron
        """
        attrs = {}
        attrs['L3'] = cls.generate_l3(cluster)
        attrs['L2'] = cls.generate_l2(cluster)
        attrs['predefined_networks'] = \
            cls.generate_predefined_networks(cluster)

        if cluster.release.operating_system == 'RHEL':
            attrs['amqp'] = {'provider': 'qpid-rh'}

        cluster_attrs = Cluster.get_attributes(cluster).editable
        if 'nsx_plugin' in cluster_attrs and \
                cluster_attrs['nsx_plugin']['metadata']['enabled']:
            attrs['L2']['provider'] = 'nsx'

        return attrs

    @classmethod
    def generate_network_scheme(cls, node):

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

        nm = objects.Node.get_network_manager(node)
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
            netgroup = nm.get_node_network_by_netname(node, ngname)
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
            netgroup = nm.get_node_network_by_netname(node, ngname)
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
        if node.cluster.network_config.segmentation_type == 'vlan':
            attrs['endpoints']['br-prv'] = {'IP': 'none'}
            attrs['roles']['private'] = 'br-prv'

            attrs['transformations'].append({
                'action': 'add-br',
                'name': 'br-prv',
            })

            attrs['transformations'].append({
                'action': 'add-patch',
                'bridges': [
                    'br-%s' % nm.get_node_interface_by_netname(
                        node.id,
                        'private'
                    ).name,
                    'br-prv'
                ]
            })
        elif node.cluster.network_config.segmentation_type == 'gre':
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
                        cluster.network_config.segmentation_type == 'vlan':
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
    def _generate_external_network(cls, cluster):
        public_cidr, public_gw = db().query(
            NetworkGroup.cidr,
            NetworkGroup.gateway
        ).filter_by(
            group_id=Cluster.get_default_group(cluster).id,
            name='public'
        ).first()

        return {
            "L3": {
                "subnet": public_cidr,
                "gateway": public_gw,
                "nameservers": [],
                "floating": utils.join_range(
                    cluster.network_config.floating_ranges[0]),
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
        return {
            "net04_ext": cls._generate_external_network(cluster),
            "net04": cls._generate_internal_network(cluster)
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
        if cluster.network_config.segmentation_type == 'gre':
            res["tunnel_id_ranges"] = utils.join_range(
                cluster.network_config.gre_id_range)
        elif cluster.network_config.segmentation_type == 'vlan':
            res["phys_nets"]["physnet2"] = {
                "bridge": "br-prv",
                "vlan_range": utils.join_range(
                    cluster.network_config.vlan_range)
            }

        # Set non-default ml2 configurations
        attrs = Cluster.get_attributes(cluster).editable
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
        attrs = Cluster.get_attributes(cluster).editable
        if 'nsx_plugin' in attrs and \
                attrs['nsx_plugin']['metadata']['enabled']:
            dhcp_attrs = l3.setdefault('dhcp_agent', {})
            dhcp_attrs['enable_isolated_metadata'] = True
            dhcp_attrs['enable_metadata_network'] = True

        return l3


class NeutronNetworkDeploymentSerializer51(NeutronNetworkDeploymentSerializer):

    @classmethod
    def _generate_external_network(cls, cluster):
        ext_netw = super(NeutronNetworkDeploymentSerializer51, cls).\
            _generate_external_network(cluster)
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
    def generate_network_scheme(cls, node):
        attrs = super(NeutronNetworkDeploymentSerializer60, cls). \
            generate_network_scheme(node)

        for item in attrs.get('transformations', ()):
            if 'tags' in item:
                item['vlan_ids'] = item['tags']

        # Include information about all subnets that don't belong to this node.
        # This is used during deployment to configure routes to all other
        # networks in the environment.
        nm = objects.Node.get_network_manager(node)
        other_nets = nm.get_networks_not_on_node(node)

        netgroup_mapping = [
            ('storage', 'br-storage'),
            ('management', 'br-mgmt'),
            ('fuelweb_admin', 'br-fw-admin'),
        ]
        if objects.Node.should_have_public(node):
            netgroup_mapping.append(('public', 'br-ex'))

        for ngname, brname in netgroup_mapping:
            netgroup = nm.get_node_network_by_netname(node, ngname)
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
    def generate_routes(cls, node, attrs, nm, netgroup_mapping, netgroups):
        other_nets = nm.get_networks_not_on_node(node)

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
        if node.cluster.network_config.segmentation_type == 'vlan':
            transformations.append(
                cls.add_bridge('br-prv', provider='ovs'))

            if not prv_base_ep:
                prv_base_ep = 'br-aux'
                transformations.append(cls.add_bridge(prv_base_ep))

            transformations.append(cls.add_patch(
                bridges=['br-prv', prv_base_ep],
                provider='ovs',
                mtu=65000))

        elif node.cluster.network_config.segmentation_type == 'gre':
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
    def generate_network_scheme(cls, node):

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
            attrs['endpoints']['br-ex'] = {}
            attrs['endpoints']['br-floating'] = {'IP': 'none'}
            attrs['roles']['ex'] = 'br-ex'
            attrs['roles']['neutron/floating'] = 'br-floating'

        nm = objects.Node.get_network_manager(node)

        # Populate IP and GW information to endpoints.
        netgroup_mapping = [
            ('storage', 'br-storage'),
            ('management', 'br-mgmt'),
            ('fuelweb_admin', 'br-fw-admin'),
        ]
        if is_public:
            netgroup_mapping.append(('public', 'br-ex'))

        if node.cluster.network_config.segmentation_type == 'gre':
            netgroup_mapping.append(('private', 'br-mesh'))
            attrs['endpoints']['br-mesh'] = {}
            attrs['roles']['neutron/mesh'] = 'br-mesh'

        netgroups = {}
        nets_by_ifaces = defaultdict(list)
        for ngname, brname in netgroup_mapping:
            # Here we get a dict with network description for this particular
            # node with its assigned IPs and device names for each network.
            netgroup = nm.get_node_network_by_netname(node, ngname)
            if netgroup.get('ip'):
                attrs['endpoints'][brname] = {'IP': [netgroup['ip']]}
            netgroups[ngname] = netgroup
            nets_by_ifaces[netgroup['dev']].append({
                'br_name': brname,
                'vlan_id': netgroup['vlan']
            })

        # Add gateway.
        if is_public:
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
        if node.cluster.network_config.segmentation_type == 'vlan':
            attrs['endpoints']['br-prv'] = {'IP': 'none'}
            attrs['roles']['neutron/private'] = 'br-prv'

            netgroup = nm.get_node_network_by_netname(node, 'private')
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
            cls.generate_routes(node, attrs, nm, netgroup_mapping, netgroups)

        attrs = cls.generate_driver_information(node, attrs, nm)

        return attrs

    @classmethod
    def generate_driver_information(cls, node, network_scheme, nm):

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
            netgroup = nm.get_node_network_by_netname(node, ngname)
            ep_dict = endpoints[brname]['vendor_specific']
            ep_dict['phy_interfaces'] = \
                cls.get_phy_interfaces(bonds_map, netgroup)
            if netgroup['vlan'] > 1:
                ep_dict['vlans'] = netgroup['vlan']

        if node.cluster.network_config.segmentation_type == 'vlan':
            private_ep = endpoints[network_mapping['neutron/private']]
            netgroup = nm.get_node_network_by_netname(node, 'private')
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
