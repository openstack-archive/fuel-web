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

from netaddr import IPNetwork
from sqlalchemy import and_

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.network.manager import NetworkManager
from nailgun.network.neutron import NeutronManager
from nailgun.settings import settings
from nailgun.task.helpers import TaskHelper
from nailgun.utils import dict_merge
from nailgun.volumes import manager as VolumeManager


class Priority(object):
    """Node with priority 0 will be deployed first.
    We have step equal 100 because we want to allow
    user redefine deployment order and he can use free space
    between prioriries.
    """

    def __init__(self):
        self.step = 100
        self.priority = 0

    @property
    def next(self):
        self.priority += self.step
        return self.priority

    @property
    def current(self):
        return self.priority


def get_nodes_not_for_deletion(cluster):
    """All clusters nodes except nodes for deletion."""
    return db().query(Node).filter(
        and_(Node.cluster == cluster,
             False == Node.pending_deletion)).order_by(Node.id)


class DeploymentMultinodeSerializer(object):

    @classmethod
    def serialize(cls, cluster, nodes):
        """Method generates facts which
        through an orchestrator passes to puppet
        """
        nodes = cls.serialize_nodes(nodes)
        common_attrs = cls.get_common_attrs(cluster)

        cls.set_deployment_priorities(nodes)

        return [dict_merge(node, common_attrs) for node in nodes]

    @classmethod
    def get_common_attrs(cls, cluster):
        """Cluster attributes."""
        attrs = cluster.attributes.merged_attrs_values()
        attrs['deployment_mode'] = cluster.mode
        attrs['deployment_id'] = cluster.id
        attrs['nodes'] = cls.node_list(get_nodes_not_for_deletion(cluster))

        for node in attrs['nodes']:
            if node['role'] in 'cinder':
                attrs['use_cinder'] = True

        attrs = dict_merge(
            attrs,
            cls.get_net_provider_serializer(cluster).get_common_attrs(cluster,
                                                                      attrs))

        return attrs

    @classmethod
    def node_list(cls, nodes):
        """Generate nodes list. Represents
        as "nodes" parameter in facts.
        """
        node_list = []

        for node in nodes:
            for role in node.all_roles:
                node_list.append({
                    'uid': node.uid,
                    'fqdn': node.fqdn,
                    'name': TaskHelper.make_slave_name(node.id),
                    'role': role})

        return node_list

    @classmethod
    def by_role(cls, nodes, role):
        return filter(lambda node: node['role'] == role, nodes)

    @classmethod
    def not_roles(cls, nodes, roles):
        return filter(lambda node: node['role'] not in roles, nodes)

    @classmethod
    def set_deployment_priorities(cls, nodes):
        """Set priorities of deployment."""
        prior = Priority()

        for n in cls.by_role(nodes, 'controller'):
            n['priority'] = prior.next

        other_nodes_prior = prior.next
        for n in cls.not_roles(nodes, 'controller'):
            n['priority'] = other_nodes_prior

    @classmethod
    def serialize_nodes(cls, nodes):
        """Serialize node for each role.
        For example if node has two roles then
        in orchestrator will be passed two serialized
        nodes.
        """
        serialized_nodes = []
        for node in nodes:
            for role in node.all_roles:
                serialized_nodes.append(cls.serialize_node(node, role))
        return serialized_nodes

    @classmethod
    def serialize_node(cls, node, role):
        """Serialize node, then it will be
        merged with common attributes
        """
        node_attrs = {
            # Yes, uid is really should be a string
            'uid': node.uid,
            'fqdn': node.fqdn,
            'status': node.status,
            'role': role,
            'glance': {
                'image_cache_max_size': VolumeManager.calc_glance_cache_size(
                    node.attributes.volumes)
            },
            # TODO (eli): need to remove, requried
            # for fucking fake thread only
            'online': node.online
        }

        node_attrs.update(
            cls.get_net_provider_serializer(node.cluster).get_node_attrs(node))

        return node_attrs

    @classmethod
    def get_net_provider_serializer(cls, cluster):
        if cluster.net_provider == 'nova_network':
            return NovaNetworkDeploymentSerializer
        else:
            return NeutronNetworkDeploymentSerializer


class DeploymentHASerializer(DeploymentMultinodeSerializer):
    """Serializer for ha mode."""

    @classmethod
    def serialize(cls, cluster, nodes):
        serialized_nodes = super(
            DeploymentHASerializer,
            cls
        ).serialize(cluster, nodes)
        cls.set_primary_controller(serialized_nodes)

        return serialized_nodes

    @classmethod
    def set_primary_controller(cls, nodes):
        """Set primary controller for the first controller
        node if it not set yet
        """
        sorted_nodes = sorted(
            nodes, key=lambda node: int(node['uid']))

        primary_controller = cls.filter_by_roles(
            sorted_nodes, ['primary-controller'])

        if not primary_controller:
            controllers = cls.filter_by_roles(
                sorted_nodes, ['controller'])
            if controllers:
                controllers[0]['role'] = 'primary-controller'

    @classmethod
    def get_last_controller(cls, nodes):
        sorted_nodes = sorted(
            nodes, key=lambda node: int(node['uid']))

        controller_nodes = cls.filter_by_roles(
            sorted_nodes, ['controller', 'primary-controller'])
        return {'last_controller': controller_nodes[-1]['name']}

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

    @classmethod
    def get_common_attrs(cls, cluster):
        """Common attributes for all facts
        """
        common_attrs = super(
            DeploymentHASerializer,
            cls
        ).get_common_attrs(cluster)

        for ng in cluster.network_groups:
            if ng.meta.get("assign_vip"):
                common_attrs[ng.name + '_vip'] = NetworkManager.assign_vip(
                    cluster.id, ng.name)

        common_attrs['mp'] = [
            {'point': '1', 'weight': '1'},
            {'point': '2', 'weight': '2'}]

        sorted_nodes = sorted(
            common_attrs['nodes'], key=lambda node: int(node['uid']))

        controller_nodes = cls.filter_by_roles(
            sorted_nodes, ['controller', 'primary-controller'])
        common_attrs['last_controller'] = controller_nodes[-1]['name']

        # Assign primary controller in nodes list
        cls.set_primary_controller(common_attrs['nodes'])

        return common_attrs

    @classmethod
    def filter_by_roles(cls, nodes, roles):
        return filter(
            lambda node: node['role'] in roles, nodes)

    @classmethod
    def set_deployment_priorities(cls, nodes):
        """Set priorities of deployment for HA mode."""
        prior = Priority()

        primary_swift_proxy_piror = prior.next
        for n in cls.by_role(nodes, 'primary-swift-proxy'):
            n['priority'] = primary_swift_proxy_piror

        swift_proxy_prior = prior.next
        for n in cls.by_role(nodes, 'swift-proxy'):
            n['priority'] = swift_proxy_prior

        storage_prior = prior.next
        for n in cls.by_role(nodes, 'storage'):
            n['priority'] = storage_prior

        # Deploy primary-controller
        for n in cls.by_role(nodes, 'primary-controller'):
            n['priority'] = prior.next

        # Then deploy other controllers one by one
        for n in cls.by_role(nodes, 'controller'):
            n['priority'] = prior.next

        other_nodes_prior = prior.next
        for n in cls.not_roles(nodes, ['primary-swift-proxy',
                                       'swift-proxy',
                                       'storage',
                                       'primary-controller',
                                       'controller',
                                       'quantum']):
            n['priority'] = other_nodes_prior


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
        raise NotImplemented

    @classmethod
    def network_provider_node_attrs(cls, cluster, node):
        raise NotImplemented

    @classmethod
    def get_net_provider_serializer(cls, cluster):
        if cluster.net_provider == 'nova_network':
            return NovaNetworkDeploymentSerializer
        else:
            return NeutronNetworkDeploymentSerializer

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
        network_manager = NetworkManager
        admin_ip = network_manager.get_admin_ip_for_node(node)
        admin_ip = IPNetwork(admin_ip)

        # Assign prefix from admin network
        admin_net = IPNetwork(network_manager.get_admin_network_group().cidr)
        admin_ip.prefixlen = admin_net.prefixlen

        return str(admin_ip)


class NovaNetworkDeploymentSerializer(NetworkDeploymentSerializer):

    @classmethod
    def network_provider_cluster_attrs(cls, cluster):
        return {'novanetwork_parameters': cls.novanetwork_attrs(cluster),
                'dns_nameservers': cluster.dns_nameservers}

    @classmethod
    def network_provider_node_attrs(cls, cluster, node):
        network_data = node.network_data
        interfaces = cls.configure_interfaces(node)
        cls.__add_hw_interfaces(interfaces, node.meta['interfaces'])

        # Interfaces assingment
        attrs = {'network_data': interfaces}
        attrs.update(cls.interfaces_list(network_data))

        if cluster.net_manager == 'VlanManager':
            attrs.update(cls.add_vlan_interfaces(node))

        return attrs

    @classmethod
    def novanetwork_attrs(cls, cluster):
        """Network configuration
        """
        attrs = {'network_manager': cluster.net_manager}

        fixed_net = db().query(NetworkGroup).filter_by(
            cluster_id=cluster.id).filter_by(name='fixed').first()

        # network_size is required for all managers, otherwise
        # puppet will use default (255)
        attrs['network_size'] = fixed_net.network_size
        if attrs['network_manager'] == 'VlanManager':
            attrs['num_networks'] = fixed_net.amount
            attrs['vlan_start'] = fixed_net.vlan_start

        return attrs

    @classmethod
    def add_vlan_interfaces(cls, node):
        """Assign fixed_interfaces and vlan_interface.
        They should be equal.
        """
        fixed_interface = NetworkManager._get_interface_by_network_name(
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

            # floating and public are on the same interface
            # so, just skip floating
            if network_name == 'floating':
                continue

            name = cls.__make_interface_name(network.get('dev'),
                                             network.get('vlan'))

            interfaces.setdefault(name, {'interface': name, 'ipaddr': []})

            interface = interfaces[name]
            if network.get('ip'):
                interface['ipaddr'].append(network.get('ip'))

            # Add gateway for public
            if network_name == 'admin':
                admin_ip_addr = cls.get_admin_ip_w_prefix(node)
                interface['ipaddr'].append(admin_ip_addr)
            elif network_name == 'public' and network.get('gateway'):
                interface['gateway'] = network['gateway']

            if len(interface['ipaddr']) == 0:
                interface['ipaddr'] = 'none'

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
            interfaces['%s_interface' % network['name']] = \
                cls.__make_interface_name(
                    network.get('dev'),
                    network.get('vlan'))

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
                    mgmt_cidr = NetworkManager.get_node_network_by_netname(
                        node.id,
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
        neutron_config = cluster.neutron_config
        attrs['L3'] = neutron_config.L3 or {
            'use_namespaces': True
        }
        attrs['L2'] = neutron_config.L2
        attrs['L2']['segmentation_type'] = neutron_config.segmentation_type

        join_range = lambda r: (":".join(map(str, r)) if r else None)

        for net, net_conf in attrs['L2']['phys_nets'].iteritems():
            net_conf['vlan_range'] = join_range(
                net_conf['vlan_range']
            )
            attrs['L2']['phys_nets'][net] = net_conf
        if attrs['L2'].get('tunnel_id_ranges'):
            attrs['L2']['tunnel_id_ranges'] = join_range(
                attrs['L2']['tunnel_id_ranges']
            )

        attrs['predefined_networks'] = neutron_config.predefined_networks

        nets_l2_configs = {
            "net04_ext": {
                "network_type": "flat",
                "segment_id": None,
                "router_ext": True,
                "physnet": "physnet1"
            },
            "net04": {
                "network_type": cluster.net_segment_type,
                "segment_id": None,
                "router_ext": False,
                "physnet": "physnet2"
            }
        }

        pub = filter(lambda ng: ng.name == 'public', cluster.network_groups)[0]

        for net, net_conf in attrs['predefined_networks'].iteritems():
            cidr = net_conf["L3"].pop("cidr")
            if net == "net04_ext":
                net_conf["L3"]["subnet"] = pub.cidr
                if pub.gateway:
                    net_conf["L3"]["gateway"] = pub.gateway
                else:
                    net_conf["L3"]["gateway"] = str(IPNetwork(pub.cidr)[1])
            else:
                net_conf["L3"]["subnet"] = cidr
                if not net_conf["L3"]["gateway"]:
                    net_conf["L3"]["gateway"] = str(IPNetwork(cidr)[1])
            net_conf["L3"]["floating"] = join_range(
                net_conf["L3"]["floating"]
            )
            enable_dhcp = False if net == "net04_ext" else True
            net_conf['L3']['enable_dhcp'] = enable_dhcp

            net_conf["L2"] = nets_l2_configs[net]
            net_conf['tenant'] = 'admin'
            net_conf["shared"] = False

            attrs['predefined_networks'][net] = net_conf

        if cluster.release.operating_system == 'RHEL':
            if 'amqp' not in attrs:
                attrs['amqp'] = {}
            elif not isinstance(attrs.get('amqp'), dict):
                # FIXME Raise some meaningful exception.
                pass
            attrs['amqp']['provider'] = 'qpid-rh'

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
                'br-ex': {},
                'br-mgmt': {},
                'br-fw-admin': {},
            },
            'roles': {
                'ex': 'br-ex',
                'management': 'br-mgmt',
                'storage': 'br-storage',
                'fw-admin': 'br-fw-admin',
            },
            'transformations': []
        }

        nm = NeutronManager
        iface_types = consts.NETWORK_INTERFACE_TYPES

        # Add a dynamic data to a structure.

        use_vlan_splinters = node.cluster.attributes.editable['common'].get(
            'vlan_splinters', {}
        ).get('value')

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
        # to provide a right ordering of ipdown/ifup operations with
        # IP interfaces.
        for brname in ('br-ex', 'br-mgmt', 'br-storage', 'br-fw-admin'):
            attrs['transformations'].append({
                'action': 'add-br',
                'name': brname
            })

        # Populate IP address information to endpoints.
        netgroup_mapping = [
            ('storage', 'br-storage'),
            ('public', 'br-ex'),
            ('management', 'br-mgmt'),
            ('fuelweb_admin', 'br-fw-admin'),
        ]
        netgroups = {}
        for ngname, brname in netgroup_mapping:
            # Here we get a dict with network description for this particular
            # node with its assigned IPs and device names for each network.
            netgroup = nm.get_node_network_by_netname(node.id, ngname)
            attrs['endpoints'][brname]['IP'] = [netgroup['ip']]
            netgroups[ngname] = netgroup
        attrs['endpoints']['br-ex']['gateway'] = netgroups['public']['gateway']

        # Connect interface bridges to network bridges.
        for ngname, brname in netgroup_mapping:
            netgroup = nm.get_node_network_by_netname(node.id, ngname)
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
        if node.cluster.net_segment_type == 'vlan':
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
        elif node.cluster.net_segment_type == 'gre':
            attrs['roles']['mesh'] = 'br-mgmt'
        else:
            # FIXME! Should raise some exception I think.
            logger.error(
                'Invalid Neutron segmentation type: %s' %
                node.cluster.net_segment_type
            )

        return attrs

    @classmethod
    def _get_vlan_splinters_desc(cls, use_vlan_splinters, iface,
                                 cluster):
        iface_attrs = {}
        if use_vlan_splinters == 'disabled':
            iface_attrs['vlan_splinters'] = 'off'
            return iface_attrs
        iface_attrs['vlan_splinters'] = 'auto'
        trunks = [0]

        if use_vlan_splinters == 'hard':
            for ng in iface.assigned_networks_list:
                if ng.name == 'private':
                    vlan_range = cluster.neutron_config.L2.get(
                        "phys_nets", {}
                    ).get("physnet2", {}).get("vlan_range", ())
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


def serialize(cluster, nodes):
    """Serialization depends on deployment mode
    """
    TaskHelper.prepare_for_deployment(cluster.nodes)

    if cluster.mode == 'multinode':
        serializer = DeploymentMultinodeSerializer
    elif cluster.is_ha_mode:
        serializer = DeploymentHASerializer

    return serializer.serialize(cluster, nodes)
