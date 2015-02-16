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

"""Deployment serializers for orchestrator"""

from collections import defaultdict
from copy import deepcopy
from itertools import groupby

from netaddr import IPNetwork
from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

import math
import six

from nailgun import objects

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.objects import Cluster
from nailgun.settings import settings
from nailgun.utils import dict_merge
from nailgun.utils import extract_env_version
from nailgun.volumes import manager as volume_manager


def get_nodes_not_for_deletion(cluster):
    """All clusters nodes except nodes for deletion."""
    return db().query(Node).filter(
        and_(Node.cluster == cluster,
             False == Node.pending_deletion)).order_by(Node.id)


class VmwareDeploymentSerializerMixin(object):

    def generate_vmware_data(self, role, node):
        """Extend serialize data with vmware attributes
        """
        vmware_data = {}
        use_vcenter = node.cluster.attributes.editable.get('common', {}) \
            .get('use_vcenter', {}).get('value')

        if (use_vcenter and
                role in ['controller', 'primary-controller', 'cinder-vmdk']):
            compute_instances = []
            cinder_instances = []

            vmware_attributes = node.cluster.vmware_attributes.editable \
                .get('value', {})
            availability_zones = vmware_attributes \
                .get('availability_zones', {})
            glance_instance = vmware_attributes.get('glance', {})
            network = vmware_attributes.get('network', {})

            for zone in availability_zones:
                for compute in zone.get('nova_computes', {}):
                    compute_item = {
                        'availability_zone_name': zone.get('az_name', ''),
                        'vc_host': zone.get('vcenter_host', ''),
                        'vc_user': zone.get('vcenter_username', ''),
                        'vc_password': zone.get('vcenter_password', ''),
                        'service_name': compute.get('service_name', ''),
                        'vc_cluster': compute.get('vshpere_cluster', ''),
                        'datastore_regex': compute.get('datastore_regex', '')
                    }

                    compute_instances.append(compute_item)

                cinder_instance = zone.get('cinder', {})
                if cinder_instance.get('enable'):
                    cinder_item = {
                        'availability_zone_name': zone.get('az_name', ''),
                        'vc_host': zone.get('vcenter_host', ''),
                        'vc_user': zone.get('vcenter_username', ''),
                        'vc_password': zone.get('vcenter_password', '')
                    }

                    cinder_instances.append(cinder_item)

            vmware_data['use_vcenter'] = True

            if compute_instances:
                vmware_data['vcenter'] = {
                    'esxi_vlan_interface':
                    network.get('esxi_vlan_interface', ''),
                    'computes': compute_instances
                }

            if cinder_instances:
                vmware_data['cinder'] = {
                    'instances': cinder_instances
                }

            if glance_instance:
                vmware_data['glance'] = {
                    'vc_host': glance_instance.get('vcenter_host', ''),
                    'vc_user': glance_instance.get('vcenter_username', ''),
                    'vc_password': glance_instance.get('vcenter_password', '')
                }

        return vmware_data


class NetworkDeploymentSerializer(object):

    @classmethod
    def update_nodes_net_info(cls, cluster, nodes):
        """Adds information about networks to each node."""
        for node in get_nodes_not_for_deletion(cluster):
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
        node_attrs = {'network_scheme': cls.generate_network_scheme(node)}
        return node_attrs

    @classmethod
    def subiface_name(cls, iface_name, net_descr):
        if not net_descr['vlan_id']:
            return iface_name
        else:
            return "{0}.{1}".format(iface_name, net_descr['vlan_id'])

    @classmethod
    def generate_network_scheme(cls, node):

        # Create network scheme structure and fill it with static values.
        attrs = {
            'version': '1.1',
            'provider': 'lnx',
            'interfaces': {},
            'endpoints': {
                'br-storage': {},
                'br-mgmt': {},
                'br-fw-admin': {},
                'br-ex': {}
            },
            'roles': {
                'storage': 'br-storage',
                'management': 'br-mgmt',
                'fw-admin': 'br-fw-admin',
                'ex': 'br-ex'
            },
            'transformations': []
        }

        brnames = ['br-fw-admin', 'br-ex', 'br-mgmt', 'br-storage']

        netgroup_mapping = [
            ('storage', 'br-storage'),
            ('management', 'br-mgmt'),
            ('fuelweb_admin', 'br-fw-admin'),
            ('public', 'br-ex'),
        ]

        nm = objects.Node.get_network_manager(node)
        iface_types = consts.NETWORK_INTERFACE_TYPES

        # add VlanManager-related objects
        if node.cluster.network_config.net_manager == 'VlanManager':
            # fixed_interface_name = nm._get_interface_by_network_name(
            #     node.id, 'fixed').name
            attrs['endpoints']['br-fixed'] = {}
            attrs['endpoints']['br-vlan'] = {}
            attrs['roles']['fixed'] = 'br-fixed'
            attrs['roles']['vlan'] = 'br-vlan'
            brnames.extend(['br-fixed', 'br-vlan'])
            netgroup_mapping.extend([
                ('fixed', 'br-fixed'),
                ('fixed', 'br-vlan')
            ])

        # Populate IP address information to endpoints.
        netgroups = {}
        nets_by_ifaces = defaultdict(list)
        for ngname, brname in netgroup_mapping:
            # Here we get a dict with network description for this particular
            # node with its assigned IPs and device names for each network.
            netgroup = nm.get_node_network_by_netname(node, ngname)
            if netgroup.get('ip'):
                attrs['endpoints'][brname]['IP'] = [netgroup['ip']]
            netgroups[ngname] = netgroup
            nets_by_ifaces[netgroup['dev']].append({
                'br_name': brname,
                'vlan_id': netgroup['vlan']
            })

        attrs['endpoints']['br-ex']['gateway'] = \
            netgroups['public']['gateway']

        # Add bridges for network roles.
        for brname in brnames:
            attrs['transformations'].append({
                'action': 'add-br',
                'name': brname
            })

        # Fill up interfaces and bonds.
        bonded_ifaces = [x for x in node.nic_interfaces if x.bond]
        for iface in node.interfaces:
            if iface.type == iface_types.ether:
                attrs['interfaces'][iface.name] = {}
            if iface in bonded_ifaces:
                # Add ports for all tagged networks on every slave NIC.
                if iface.name in nets_by_ifaces:
                    for net in nets_by_ifaces[iface.name]:
                        if net['vlan_id']:
                            attrs['transformations'].append({
                                'action': 'add-port',
                                'bridge': net['br_name'],
                                'name': cls.subiface_name(iface.name, net)
                            })
                # Don't create anything for untagged networks on slave NICs.
                continue

            if iface.type == iface_types.ether:
                # Add ports for all networks on every unbonded NIC.
                if iface.name in nets_by_ifaces:
                    for net in nets_by_ifaces[iface.name]:
                        attrs['transformations'].append({
                            'action': 'add-port',
                            'bridge': net['br_name'],
                            'name': cls.subiface_name(iface.name, net)
                        })
            elif iface.type == iface_types.bond:
                # Add bonds and connect untagged networks' bridges to them.
                # There can be no more than one untagged network on each bond.
                bond = {
                    'action': 'add-bond',
                    'name': iface.name,
                    'interfaces': [x['name'] for x in iface.slaves],
                    'bond_properties': nm.get_lnx_bond_properties(iface),
                    'interface_properties': nm.get_iface_properties(iface)
                }
                if iface.name in nets_by_ifaces:
                    for net in nets_by_ifaces[iface.name]:
                        if not net['vlan_id']:
                            bond['bridge'] = net['br_name']
                            break
                attrs['transformations'].append(bond)
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
                if ng.name == 'private':
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
        join_range = lambda r: (":".join(map(str, r)) if r else None)
        return {
            "L3": {
                "subnet": public_cidr,
                "gateway": public_gw,
                "nameservers": [],
                "floating": join_range(
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
    def generate_network_scheme(cls, node):

        # Create a data structure and fill it with static values.

        attrs = {
            'version': '1.1',
            'provider': 'lnx',
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

        is_public = objects.Node.should_have_public(node)
        if is_public:
            attrs['endpoints']['br-ex'] = {}
            attrs['endpoints']['br-floating'] = {'IP': 'none'}
            attrs['roles']['ex'] = 'br-ex'
            attrs['roles']['floating'] = 'br-floating'

        nm = objects.Node.get_network_manager(node)
        iface_types = consts.NETWORK_INTERFACE_TYPES

        # Populate IP and GW information to endpoints.
        netgroup_mapping = [
            ('storage', 'br-storage'),
            ('management', 'br-mgmt'),
            ('fuelweb_admin', 'br-fw-admin'),
        ]
        if is_public:
            netgroup_mapping.append(('public', 'br-ex'))

        netgroups = {}
        nets_by_ifaces = defaultdict(list)
        for ngname, brname in netgroup_mapping:
            # Here we get a dict with network description for this particular
            # node with its assigned IPs and device names for each network.
            netgroup = nm.get_node_network_by_netname(node, ngname)
            if netgroup.get('ip'):
                attrs['endpoints'][brname]['IP'] = [netgroup['ip']]
            # if netgroup.get('gateway'):
            #     attrs['endpoints'][brname]['gateway'] = netgroup['gateway']
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
            attrs['endpoints']['br-fw-admin']['gateway'] = settings.MASTER_IP

        # Add bridges for networks.
        brnames = ['br-fw-admin', 'br-mgmt', 'br-storage']
        if is_public:
            brnames.append('br-ex')

        for brname in brnames:
            attrs['transformations'].append({
                'action': 'add-br',
                'name': brname
            })

        if is_public:
            # br-floating is an OVS bridge and it's always connected with br-ex
            attrs['transformations'].append({
                'action': 'add-br',
                'name': 'br-floating',
                'provider': 'ovs'
            })
            attrs['transformations'].append({
                'action': 'add-patch',
                'bridges': [
                    'br-ex',
                    'br-floating'
                ],
                'provider': 'ovs2lnx'
            })

        # Dance around Neutron segmentation type.
        if node.cluster.network_config.segmentation_type == 'vlan':
            attrs['endpoints']['br-prv'] = {'IP': 'none'}
            attrs['roles']['private'] = 'br-prv'

            attrs['transformations'].append({
                'action': 'add-br',
                'name': 'br-prv',
                'provider': 'ovs'
            })
            attrs['transformations'].append({
                'action': 'add-br',
                'name': 'br-aux',
            })
            attrs['transformations'].append({
                'action': 'add-patch',
                'bridges': [
                    'br-aux',
                    'br-prv'
                ],
                'provider': 'ovs2lnx'
            })

            netgroup = nm.get_node_network_by_netname(node, 'private')
            nets_by_ifaces[netgroup['dev']].append({
                'br_name': 'br-aux',
                'vlan_id': None
            })
        elif node.cluster.network_config.segmentation_type == 'gre':
            attrs['roles']['mesh'] = 'br-mgmt'

        # Fill up interfaces and bonds.
        bonded_ifaces = [x for x in node.nic_interfaces if x.bond]
        for iface in node.interfaces:
            if iface.type == iface_types.ether:
                attrs['interfaces'][iface.name] = {}
            if iface in bonded_ifaces:
                # Add ports for all tagged networks on every slave NIC.
                if iface.name in nets_by_ifaces:
                    for net in nets_by_ifaces[iface.name]:
                        if net['vlan_id']:
                            attrs['transformations'].append({
                                'action': 'add-port',
                                'bridge': net['br_name'],
                                'name': cls.subiface_name(iface.name, net)
                            })
                # Don't create anything for untagged networks on slave NICs.
                continue

            if iface.type == iface_types.ether:
                # Add ports for all networks on every unbonded NIC.
                if iface.name in nets_by_ifaces:
                    for net in nets_by_ifaces[iface.name]:
                        attrs['transformations'].append({
                            'action': 'add-port',
                            'bridge': net['br_name'],
                            'name': cls.subiface_name(iface.name, net)
                        })
            elif iface.type == iface_types.bond:
                # Add bonds and connect untagged networks' bridges to them.
                # There can be no more than one untagged network on each bond.
                bond = {
                    'action': 'add-bond',
                    'name': iface.name,
                    'interfaces': sorted(x['name'] for x in iface.slaves),
                    'bond_properties': nm.get_lnx_bond_properties(iface),
                    'interface_properties': nm.get_iface_properties(iface)
                }
                if iface.name in nets_by_ifaces:
                    for net in nets_by_ifaces[iface.name]:
                        if not net['vlan_id']:
                            bond['bridge'] = net['br_name']
                            break
                attrs['transformations'].append(bond)

        return attrs


class GraphBasedSerializer(object):

    def __init__(self, graph):
        self.graph = graph

    def set_deployment_priorities(self, nodes):
        self.graph.add_priorities(nodes)

    def set_tasks(self, nodes):
        for node in nodes:
            node['tasks'] = self.graph.deploy_task_serialize(node)


class DeploymentMultinodeSerializer(GraphBasedSerializer):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer

    critical_roles = ['controller', 'ceph-osd', 'primary-mongo']

    def serialize(self, cluster, nodes, ignore_customized=False):
        """Method generates facts which
        through an orchestrator passes to puppet
        """
        serialized_nodes = []
        keyfunc = lambda node: bool(node.replaced_deployment_info)
        for customized, node_group in groupby(nodes, keyfunc):
            if customized and not ignore_customized:
                serialized_nodes.extend(
                    self.serialize_customized(cluster, node_group))
            else:
                serialized_nodes.extend(self.serialize_generated(
                    cluster, node_group))
        return serialized_nodes

    def serialize_generated(self, cluster, nodes):
        nodes = self.serialize_nodes(nodes)
        common_attrs = self.get_common_attrs(cluster)

        self.set_deployment_priorities(nodes)
        self.set_critical_nodes(nodes)
        self.set_tasks(nodes)
        return [dict_merge(node, common_attrs) for node in nodes]

    def serialize_customized(self, cluster, nodes):
        serialized = []
        release_data = objects.Release.get_orchestrator_data_dict(
            self.current_release(cluster))
        for node in nodes:
            for role_data in node.replaced_deployment_info:
                role_data.update(release_data)
                serialized.append(role_data)
        return serialized

    def get_common_attrs(self, cluster):
        """Cluster attributes."""
        attrs = objects.Attributes.merged_attrs_values(cluster.attributes)
        release = self.current_release(cluster)

        attrs['deployment_mode'] = cluster.mode
        attrs['deployment_id'] = cluster.id
        attrs['openstack_version_prev'] = getattr(
            self.previous_release(cluster), 'version', None)
        attrs['openstack_version'] = release.version
        attrs['fuel_version'] = cluster.fuel_version
        attrs.update(
            objects.Release.get_orchestrator_data_dict(release)
        )
        attrs['nodes'] = self.node_list(get_nodes_not_for_deletion(cluster))

        for node in attrs['nodes']:
            if node['role'] in 'cinder':
                attrs['use_cinder'] = True

        self.set_storage_parameters(cluster, attrs)
        self.set_primary_mongo(attrs['nodes'])

        net_serializer = self.get_net_provider_serializer(cluster)
        net_common_attrs = net_serializer.get_common_attrs(cluster, attrs)
        attrs = dict_merge(attrs, net_common_attrs)

        return attrs

    def current_release(self, cluster):
        """Actual cluster release."""
        return objects.Release.get_by_uid(cluster.pending_release_id) \
            if cluster.status == consts.CLUSTER_STATUSES.update \
            else cluster.release

    def previous_release(self, cluster):
        """Returns previous release.

        :param cluster: a ``Cluster`` instance to retrieve release from
        :returns: a ``Release`` instance of previous release or ``None``
            in case there's no previous release (fresh deployment).
        """
        if cluster.status == consts.CLUSTER_STATUSES.update:
            return cluster.release
        return None

    def set_storage_parameters(self, cluster, attrs):
        """Generate pg_num as the number of OSDs across the cluster
        multiplied by 100, divided by Ceph replication factor, and
        rounded up to the nearest power of 2.
        """
        osd_num = 0
        nodes = db().query(Node). \
            filter(or_(
                Node.role_list.any(name='ceph-osd'),
                Node.pending_role_list.any(name='ceph-osd'))). \
            filter(Node.cluster == cluster). \
            options(joinedload('attributes'))
        for node in nodes:
            for disk in node.attributes.volumes:
                for part in disk.get('volumes', []):
                    if part.get('name') == 'ceph' and part.get('size', 0) > 0:
                        osd_num += 1
        if osd_num > 0:
            repl = int(attrs['storage']['osd_pool_size'])
            pg_num = 2 ** int(math.ceil(math.log(osd_num * 100.0 / repl, 2)))
        else:
            pg_num = 128
        attrs['storage']['pg_num'] = pg_num

    @classmethod
    def node_list(cls, nodes):
        """Generate nodes list. Represents
        as "nodes" parameter in facts.
        """
        node_list = []

        for node in nodes:
            for role in objects.Node.all_roles(node):
                node_list.append(cls.serialize_node_for_node_list(node, role))

        return node_list

    @classmethod
    def serialize_node_for_node_list(cls, node, role):
        return {
            'uid': node.uid,
            'fqdn': node.fqdn,
            'name': objects.Node.make_slave_name(node),
            'role': role}

    # TODO(apopovych): we have more generical method 'filter_by_roles'
    def by_role(self, nodes, role):
        return filter(lambda node: node['role'] == role, nodes)

    def not_roles(self, nodes, roles):
        return filter(lambda node: node['role'] not in roles, nodes)

    def set_critical_nodes(self, nodes):
        """Set behavior on nodes deployment error
        during deployment process.
        """
        for n in nodes:
            n['fail_if_error'] = n['role'] in self.critical_roles

    def serialize_nodes(self, nodes):
        """Serialize node for each role.
        For example if node has two roles then
        in orchestrator will be passed two serialized
        nodes.
        """
        serialized_nodes = []
        for node in nodes:
            for role in objects.Node.all_roles(node):
                serialized_nodes.append(self.serialize_node(node, role))
        self.set_primary_mongo(serialized_nodes)
        return serialized_nodes

    def serialize_node(self, node, role):
        """Serialize node, then it will be
        merged with common attributes
        """
        node_attrs = {
            # Yes, uid is really should be a string
            'uid': node.uid,
            'fqdn': node.fqdn,
            'status': node.status,
            'role': role,
            # TODO (eli): need to remove, requried
            # for the fake thread only
            'online': node.online
        }

        net_serializer = self.get_net_provider_serializer(node.cluster)
        node_attrs.update(net_serializer.get_node_attrs(node))
        node_attrs.update(net_serializer.network_ranges(node.group_id))
        node_attrs.update(self.get_image_cache_max_size(node))
        node_attrs.update(self.generate_test_vm_image_data(node))

        return node_attrs

    def get_image_cache_max_size(self, node):
        images_ceph = (node.cluster.attributes['editable']['storage']
                       ['images_ceph']['value'])
        if images_ceph:
            image_cache_max_size = '0'
        else:
            image_cache_max_size = volume_manager.calc_glance_cache_size(
                node.attributes.volumes)
        return {'glance': {'image_cache_max_size': image_cache_max_size}}

    def generate_test_vm_image_data(self, node):
        # Instantiate all default values in dict.
        image_data = {
            'container_format': 'bare',
            'public': 'true',
            'disk_format': 'qcow2',
            'img_name': 'TestVM',
            'img_path': '',
            'os_name': 'cirros',
            'min_ram': 64,
            'glance_properties': '',
        }
        # Generate a right path to image.
        c_attrs = node.cluster.attributes
        if 'ubuntu' in c_attrs['generated']['cobbler']['profile']:
            img_dir = '/usr/share/cirros-testvm/'
        else:
            img_dir = '/opt/vm/'
        image_data['img_path'] = '{0}cirros-x86_64-disk.img'.format(img_dir)
        # Add default Glance property for Murano.
        glance_properties = [
            """--property murano_image_info="""
            """'{"title": "Murano Demo", "type": "cirros.demo"}'"""
        ]

        # Alternate VMWare specific values.
        if c_attrs['editable']['common']['libvirt_type']['value'] == 'vcenter':
            image_data.update({
                'disk_format': 'vmdk',
                'img_path': '{0}cirros-i386-disk.vmdk'.format(img_dir),
            })
            glance_properties.append('--property vmware_disktype=sparse')
            glance_properties.append('--property vmware_adaptertype=lsilogic')
            glance_properties.append('--property hypervisor_type=vmware')

        image_data['glance_properties'] = ' '.join(glance_properties)

        return {'test_vm_image': image_data}

    @classmethod
    def get_net_provider_serializer(cls, cluster):
        if cluster.net_provider == 'nova_network':
            return cls.nova_network_serializer
        else:
            return cls.neutron_network_serializer

    def set_primary_node(self, nodes, role, primary_node_index):
        """Set primary node for role if it not set yet.
        primary_node_index defines primary node position in nodes list
        """
        sorted_nodes = sorted(
            nodes, key=lambda node: int(node['uid']))

        primary_role = 'primary-{0}'.format(role)
        primary_node = self.filter_by_roles(
            sorted_nodes, [primary_role])
        if primary_node:
            return

        result_nodes = self.filter_by_roles(
            sorted_nodes, [role])
        if result_nodes:
            result_nodes[primary_node_index]['role'] = primary_role

    def set_primary_mongo(self, nodes):
        """Set primary mongo for the last mongo node
        node if it not set yet
        """
        self.set_primary_node(nodes, 'mongo', 0)

    def filter_by_roles(self, nodes, roles):
        return filter(
            lambda node: node['role'] in roles, nodes)


class DeploymentHASerializer(DeploymentMultinodeSerializer):
    """Serializer for ha mode."""

    critical_roles = ['primary-controller',
                      'primary-mongo',
                      'primary-swift-proxy',
                      'ceph-osd']

    def get_last_controller(self, nodes):
        sorted_nodes = sorted(
            nodes, key=lambda node: int(node['uid']))

        controller_nodes = self.filter_by_roles(
            sorted_nodes, ['controller', 'primary-controller'])

        last_controller = None
        if len(controller_nodes) > 0:
            last_controller = controller_nodes[-1]['name']

        return {'last_controller': last_controller}

    @classmethod
    def node_list(cls, nodes):
        """Node list
        """
        node_list = super(
            DeploymentHASerializer,
            cls
        ).node_list(nodes)

        for node in node_list:
            node['swift_zone'] = node['uid']

        return node_list

    def get_common_attrs(self, cluster):
        """Common attributes for all facts
        """
        common_attrs = super(
            DeploymentHASerializer,
            self
        ).get_common_attrs(cluster)

        net_manager = objects.Cluster.get_network_manager(cluster)

        for ng in cluster.network_groups:
            if ng.meta.get("assign_vip"):
                common_attrs[ng.name + '_vip'] = net_manager.assign_vip(
                    cluster.id, ng.name)

        common_attrs['mp'] = [
            {'point': '1', 'weight': '1'},
            {'point': '2', 'weight': '2'}]

        last_controller = self.get_last_controller(common_attrs['nodes'])
        common_attrs.update(last_controller)

        return common_attrs


class DeploymentMultinodeSerializer51(DeploymentMultinodeSerializer):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer51


class DeploymentHASerializer51(DeploymentHASerializer):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer51


class DeploymentMultinodeSerializer60(DeploymentMultinodeSerializer):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer60


class DeploymentHASerializer60(DeploymentHASerializer):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer60


class DeploymentMultinodeSerializer61(DeploymentMultinodeSerializer,
                                      VmwareDeploymentSerializerMixin):

    nova_network_serializer = NovaNetworkDeploymentSerializer61
    neutron_network_serializer = NeutronNetworkDeploymentSerializer61

    def serialize_node(self, node, role):
        serialized_node = super(
            DeploymentMultinodeSerializer61, self).serialize_node(node, role)
        serialized_node['user_node_name'] = node.name
        serialized_node.update(self.generate_vmware_data(role, node))

        return serialized_node

    @classmethod
    def serialize_node_for_node_list(cls, node, role):
        serialized_node = super(
            DeploymentMultinodeSerializer61,
            cls).serialize_node_for_node_list(node, role)
        serialized_node['user_node_name'] = node.name
        return serialized_node


class DeploymentHASerializer61(DeploymentHASerializer,
                               VmwareDeploymentSerializerMixin):

    nova_network_serializer = NovaNetworkDeploymentSerializer61
    neutron_network_serializer = NeutronNetworkDeploymentSerializer61

    def serialize_node(self, node, role):
        serialized_node = super(
            DeploymentHASerializer61, self).serialize_node(node, role)
        serialized_node['user_node_name'] = node.name
        serialized_node.update(self.generate_vmware_data(role, node))

        return serialized_node

    @classmethod
    def serialize_node_for_node_list(cls, node, role):
        serialized_node = super(
            DeploymentHASerializer61,
            cls).serialize_node_for_node_list(node, role)
        serialized_node['user_node_name'] = node.name
        return serialized_node

    # Alternate VMWare specific values.
    # FiXME(who): srogov
    # This a temporary workaround to keep existing functioanality
    # after fully implementation of the multi HV support and astute part
    # for multiple images support, it is need to change
    # dict image_data['test_vm_image'] to list of dicts
    def generate_test_vm_image_data(self, node):
        attrs = node.cluster.attributes
        image_data = super(
            DeploymentHASerializer61,
            self).generate_test_vm_image_data(node)

        images_data = {}
        images_data['test_vm_image'] = []
        if attrs.get('editable', {}).get('common', {}). \
           get('use_vcenter', {}).get('value') is True:
            image_vmdk_data = deepcopy(image_data['test_vm_image'])
            img_path = image_vmdk_data['img_path']. \
                replace('x86_64-disk.img', 'i386-disk.vmdk')
            image_vmdk_data.update({
                'img_name': 'TestVM-VMDK',
                'disk_format': 'vmdk',
                'img_path': img_path,
            })
            image_vmdk_data['glance_properties'] = ' '.join([
                '--property vmware_disktype=sparse',
                '--property vmware_adaptertype=lsilogic',
                '--property hypervisor_type=vmware'])
            images_data['test_vm_image'].append(image_vmdk_data)
            images_data['test_vm_image'].append(image_data['test_vm_image'])
        else:
            images_data = image_data

        return images_data


def get_serializer_for_cluster(cluster):
    """Returns a serializer depends on a given `cluster`.

    :param cluster: cluster to process
    :returns: a serializer for a given cluster
    """
    serializers_map = {
        '5.0': {
            'multinode': DeploymentMultinodeSerializer,
            'ha': DeploymentHASerializer,
        },
        '5.1': {
            'multinode': DeploymentMultinodeSerializer51,
            'ha': DeploymentHASerializer51,
        },
        '6.0': {
            'multinode': DeploymentMultinodeSerializer60,
            'ha': DeploymentHASerializer60,
        },
        '6.1': {
            'multinode': DeploymentMultinodeSerializer61,
            'ha': DeploymentHASerializer61,
        },
    }

    env_version = extract_env_version(cluster.release.version)
    env_mode = 'ha' if cluster.is_ha_mode else 'multinode'
    for version, serializers in six.iteritems(serializers_map):
        if env_version.startswith(version):
            return serializers[env_mode]

    raise errors.UnsupportedSerializer()


def serialize(orchestrator_graph, cluster, nodes, ignore_customized=False):
    """Serialization depends on deployment mode
    """
    objects.Cluster.set_primary_roles(cluster, nodes)
    objects.NodeCollection.prepare_for_deployment(cluster.nodes)
    serializer = get_serializer_for_cluster(cluster)(orchestrator_graph)

    return serializer.serialize(
        cluster, nodes, ignore_customized=ignore_customized)
