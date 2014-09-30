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
from nailgun.orchestrator import priority_serializers as ps
from nailgun.settings import settings
from nailgun.utils import dict_merge
from nailgun.utils import extract_env_version
from nailgun.volumes import manager as volume_manager


def get_nodes_not_for_deletion(cluster):
    """All clusters nodes except nodes for deletion."""
    return db().query(Node).filter(
        and_(Node.cluster == cluster,
             False == Node.pending_deletion)).order_by(Node.id)


class NetworkDeploymentSerializer(object):

    @classmethod
    def get_common_attrs(cls, cluster, attrs):
        """Cluster network attributes."""
        common = cls.network_provider_cluster_attrs(cluster)
        common.update(cls.network_ranges(cluster))
        common.update({'master_ip': settings.MASTER_IP})
        common['nodes'] = deepcopy(attrs['nodes'])

        # Addresses
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

            [n.update(addresses) for n in common['nodes']
             if n['uid'] == str(node.uid)]
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
    def network_ranges(cls, cluster):
        """Returns ranges for network groups
        except range for public network
        """
        ng_db = db().query(NetworkGroup).filter_by(cluster_id=cluster.id).all()
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
        admin_ip = network_manager.get_admin_ip_for_node(node)
        admin_ip = IPNetwork(admin_ip)

        # Assign prefix from admin network
        admin_net = IPNetwork(network_manager.get_admin_network_group().cidr)
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

            if network_name == 'admin':
                admin_ip_addr = cls.get_admin_ip_w_prefix(node)
                interface['ipaddr'].append(admin_ip_addr)
            elif network_name == 'public' and network.get('gateway'):
                interface['gateway'] = network['gateway']

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
        brnames = ['br-mgmt', 'br-storage', 'br-fw-admin']
        if objects.Node.should_have_public(node):
            brnames.append('br-ex')

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
            cluster_id=cluster.id,
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
            "tenant": "admin",
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
            "tenant": "admin",
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


class DeploymentMultinodeSerializer(object):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer

    critical_roles = ['controller', 'ceph-osd', 'primary-mongo']

    def __init__(self, priority_serializer):
        self.priority = priority_serializer

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

        attrs = dict_merge(
            attrs,
            self.get_net_provider_serializer(cluster).get_common_attrs(cluster,
                                                                       attrs))

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

    def node_list(self, nodes):
        """Generate nodes list. Represents
        as "nodes" parameter in facts.
        """
        node_list = []

        for node in nodes:
            for role in sorted(node.all_roles):
                node_list.append({
                    'uid': node.uid,
                    'fqdn': node.fqdn,
                    'name': objects.Node.make_slave_name(node),
                    'role': role})

        return node_list

    def by_role(self, nodes, role):
        return filter(lambda node: node['role'] == role, nodes)

    def not_roles(self, nodes, roles):
        return filter(lambda node: node['role'] not in roles, nodes)

    def set_deployment_priorities(self, nodes):
        """Set priorities of deployment."""
        self.priority.set_deployment_priorities(nodes)

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
            for role in sorted(node.all_roles):
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

        node_attrs.update(self.get_net_provider_serializer(
            node.cluster).get_node_attrs(node))
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
            glance_properties.append('--property vmware_adaptertype=ide')
            glance_properties.append('--property hypervisor_type=vmware')

        image_data['glance_properties'] = ' '.join(glance_properties)

        return {'test_vm_image': image_data}

    def get_net_provider_serializer(self, cluster):
        if cluster.net_provider == 'nova_network':
            return self.nova_network_serializer
        else:
            return self.neutron_network_serializer

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

    def serialize_nodes(self, nodes):
        """Serialize nodes and set primary-controller
        """
        serialized_nodes = super(
            DeploymentHASerializer, self).serialize_nodes(nodes)
        self.set_primary_controller(serialized_nodes)
        return serialized_nodes

    def set_primary_controller(self, nodes):
        """Set primary controller for the first controller
        node if it not set yet
        """
        self.set_primary_node(nodes, 'controller', 0)

    def get_last_controller(self, nodes):
        sorted_nodes = sorted(
            nodes, key=lambda node: int(node['uid']))

        controller_nodes = self.filter_by_roles(
            sorted_nodes, ['controller', 'primary-controller'])

        last_controller = None
        if len(controller_nodes) > 0:
            last_controller = controller_nodes[-1]['name']

        return {'last_controller': last_controller}

    def node_list(self, nodes):
        """Node list
        """
        node_list = super(
            DeploymentHASerializer,
            self
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

        # Assign primary controller in nodes list
        self.set_primary_controller(common_attrs['nodes'])

        return common_attrs


class DeploymentMultinodeSerializer51(DeploymentMultinodeSerializer):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer51


class DeploymentHASerializer51(DeploymentHASerializer):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer51


def create_serializer(cluster):
    """Returns a serializer depends on a given `cluster`.

    :param cluster: a cluster to process
    :returns: a serializer for a given cluster
    """
    # env-version serializer map
    serializers_map = {
        '5.0': {
            'multinode': (
                DeploymentMultinodeSerializer,
                ps.PriorityMultinodeSerializer50,
            ),
            'ha': (
                DeploymentHASerializer,
                ps.PriorityHASerializer50,
            ),
        },
        '5.1': {
            'multinode': (
                DeploymentMultinodeSerializer51,
                ps.PriorityMultinodeSerializer51,
            ),
            'ha': (
                DeploymentHASerializer51,
                ps.PriorityHASerializer51,
            ),
        },
    }

    env_version = extract_env_version(cluster.release.version)
    env_mode = 'ha' if cluster.is_ha_mode else 'multinode'

    # choose serializer
    for version, serializers in six.iteritems(serializers_map):
        if env_version.startswith(version):
            serializer, priority = serializers[env_mode]
            if cluster.pending_release_id:
                priority = {
                    'ha': ps.PriorityHASerializerPatching,
                    'multinode': ps.PriorityMultinodeSerializerPatching,
                }.get(env_mode)
            return serializer(priority())

    raise errors.UnsupportedSerializer()


def serialize(cluster, nodes, ignore_customized=False):
    """Serialization depends on deployment mode
    """
    objects.NodeCollection.prepare_for_deployment(cluster.nodes)
    serializer = create_serializer(cluster)

    return serializer.serialize(
        cluster, nodes, ignore_customized=ignore_customized)
