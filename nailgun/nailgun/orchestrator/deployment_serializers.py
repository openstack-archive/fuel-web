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

from nailgun.api.models import NetworkGroup
from nailgun.api.models import Node
from nailgun.db import db
from nailgun.errors import errors
from nailgun.network.manager import NetworkManager
from nailgun.settings import settings
from nailgun.task.helpers import TaskHelper
from netaddr import IPNetwork
from sqlalchemy import and_
from sqlalchemy import or_


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


class UpdatableDict(dict):

    def update_nested(self, common):
        for key, value in common.iteritems():
            if key in self and isinstance(self[key], dict):
                self[key].update(value)
            elif key not in self:
                self[key] = value


class OrchestratorSerializer(object):
    """Base class for orchestrator searilization."""

    @classmethod
    def serialize(cls, cluster):
        """Method generates facts which
        through an orchestrator passes to puppet
        """
        common_attrs = cls.get_common_attrs(cluster)
        nodes = list(cls.serialize_nodes(
                     cls.get_nodes_to_deployment(cluster)))

        if cluster.net_manager == 'VlanManager':
            cls.add_vlan_interfaces(nodes)

        cls.set_deployment_priorities(nodes)

        # Merge attributes of nodes with common attributes
        [node.update_nested(common_attrs) for node in nodes]
        return nodes

    @classmethod
    def get_common_attrs(cls, cluster):
        """Common attributes for all facts
        """
        attrs = cls.serialize_cluster_attrs(cluster)
        attrs['nodes'] = cls.node_list(cls.get_all_nodes(cluster))

        for node in attrs['nodes']:
            if node['role'] in 'cinder':
                attrs['use_cinder'] = True

        return attrs

    @classmethod
    def serialize_cluster_attrs(cls, cluster):
        """Cluster attributes."""
        attrs = cluster.attributes.merged_attrs_values()
        attrs['deployment_mode'] = cluster.mode
        attrs['deployment_id'] = cluster.id
        attrs['master_ip'] = settings.MASTER_IP
        attrs['novanetwork_parameters'] = cls.novanetwork_attrs(cluster)
        attrs.update(cls.network_ranges(cluster))

        return attrs

    @classmethod
    def get_nodes_to_deployment(cls, cluster):
        """Nodes which need to deploy."""
        return sorted(TaskHelper.nodes_to_deploy(cluster),
                      key=lambda node: node.id)

    @classmethod
    def get_all_nodes(cls, cluster):
        """All clusters nodes except nodes for deletion."""
        return db().query(Node).filter(
            and_(Node.cluster == cluster,
                 False == Node.pending_deletion)).order_by(Node.id)

    @classmethod
    def novanetwork_attrs(cls, cluster):
        """Network configuration
        """
        attrs = {}
        attrs['network_manager'] = cluster.net_manager

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
    def add_vlan_interfaces(cls, nodes):
        """Assign fixed_interfaces and vlan_interface.
        They should be equal.
        """
        netmanager = NetworkManager()
        for node in nodes:
            node_db = db().query(Node).get(node['uid'])

            fixed_interface = netmanager._get_interface_by_network_name(
                node_db.id, 'fixed')

            node['fixed_interface'] = fixed_interface.name
            node['vlan_interface'] = fixed_interface.name

    @classmethod
    def network_ranges(cls, cluster):
        """Returns ranges for network groups
        except range for public network
        """
        ng_db = db().query(NetworkGroup).filter_by(cluster_id=cluster.id).all()
        attrs = {}
        for net in ng_db:
            net_name = net.name + '_network_range'

            if net.name == 'floating':
                attrs[net_name] = cls.get_ip_ranges_first_last(net)
            elif net.name == 'public':
                # We shouldn't pass public_network_range attribute
                continue
            else:
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
    def serialize_nodes(cls, nodes):
        """Serialize node for each role.
        For example if node has two roles then
        in orchestrator will be passed two serialized
        nodes.
        """
        for node in nodes:
            for role in node.all_roles:
                yield cls.serialize_node(node, role)

    @classmethod
    def serialize_node(cls, node, role):
        """Serialize node, then it will be
        merged with common attributes
        """
        network_data = node.network_data
        interfaces = cls.configure_interfaces(network_data)
        cls.__add_hw_interfaces(interfaces, node.meta['interfaces'])

        node_attrs = UpdatableDict({
            # Yes, uid is really should be a string
            'uid': str(node.id),
            'fqdn': node.fqdn,
            'status': node.status,
            'role': role,
            'glance': {
                'image_cache_max_size': node.volume_manager.glance_cache_size
            },
            # Interfaces assingment
            'network_data': interfaces,

            # TODO (eli): need to remove, requried
            # for fucking fake thread only
            'online': node.online,
        })
        node_attrs.update(cls.interfaces_list(network_data))

        return node_attrs

    @classmethod
    def node_list(cls, nodes):
        """Generate nodes list. Represents
        as "nodes" parameter in facts.
        """
        node_list = []

        for node in nodes:
            network_data = node.network_data

            for role in node.all_roles:
                node_list.append({
                    # Yes, uid is really should be a string
                    'uid': str(node.id),
                    'fqdn': node.fqdn,
                    'name': TaskHelper.make_slave_name(node.id),
                    'role': role,

                    # Addresses
                    'internal_address': cls.get_addr(network_data,
                                                     'management')['ip'],
                    'internal_netmask': cls.get_addr(network_data,
                                                     'management')['netmask'],
                    'storage_address': cls.get_addr(network_data,
                                                    'storage')['ip'],
                    'storage_netmask': cls.get_addr(network_data,
                                                    'storage')['netmask'],
                    'public_address': cls.get_addr(network_data,
                                                   'public')['ip'],
                    'public_netmask': cls.get_addr(network_data,
                                                   'public')['netmask']})

        return node_list

    @classmethod
    def get_addr(cls, network_data, name):
        """Get addr for network by name
        """
        nets = filter(
            lambda net: net['name'] == name,
            network_data)

        if not nets or 'ip' not in nets[0]:
            raise errors.CanNotFindNetworkForNode(
                'Cannot find network with name: %s' % name)

        net = nets[0]['ip']
        return {
            'ip': str(IPNetwork(net).ip),
            'netmask': str(IPNetwork(net).netmask)
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

    @classmethod
    def configure_interfaces(cls, network_data):
        """Configre interfaces
        """
        interfaces = {}
        for network in network_data:
            network_name = network['name']

            # floating and public are on the same interface
            # so, just skip floating
            if network_name == 'floating':
                continue

            name = cls.__make_interface_name(network.get('dev'),
                                             network.get('vlan'))

            if name not in interfaces:
                interfaces[name] = {
                    'interface': name,
                    'ipaddr': [],
                    '_name': network_name}

            interface = interfaces[name]

            if network_name == 'admin':
                interface['ipaddr'] = 'dhcp'
            elif network.get('ip'):
                interface['ipaddr'].append(network.get('ip'))

            # Add gateway for public
            if network_name == 'public' and network.get('gateway'):
                interface['gateway'] = network['gateway']

            if len(interface['ipaddr']) == 0:
                interface['ipaddr'] = 'none'

        interfaces['lo'] = {'interface': 'lo', 'ipaddr': ['127.0.0.1/8']}

        return interfaces

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

    @staticmethod
    def update_nested_dicts(custom, common):
        """Merge two nested dictionaries.
        @custom - dict
        @common - dict
        """
        for key, value in common.iteritems():
            if key in custom and isinstance(custom[key], dict):
                custom[key].update(value)
            elif key not in custom:
                custom[key] = value


class OrchestratorHASerializer(OrchestratorSerializer):
    """Serializer for ha mode."""

    @classmethod
    def serialize(cls, cluster):
        serialized_nodes = super(
            OrchestratorHASerializer, cls).serialize(cluster)
        cls.set_primary_controller(serialized_nodes)

        return serialized_nodes

    @classmethod
    def has_controller_nodes(cls, nodes):
        for node in nodes:
            if 'controller' in node.all_roles:
                return True
        return False

    @classmethod
    def get_nodes_to_deployment(cls, cluster):
        """Get nodes for deployment
        * in case of failed controller should be redeployed
          all controllers
        * in case of failed non-controller should be
          redeployed only node which was failed
        """
        nodes = super(
            OrchestratorHASerializer, cls).get_nodes_to_deployment(cluster)

        controller_nodes = []

        # if list contain at least one controller
        if cls.has_controller_nodes(nodes):
            # retrive all controllers from cluster
            controller_nodes = db().query(Node).\
                filter(or_(
                    Node.role_list.any(name='controller'),
                    Node.pending_role_list.any(name='controller'),
                    Node.role_list.any(name='primary-controller'),
                    Node.pending_role_list.any(name='primary-controller')
                )).\
                filter(Node.cluster == cluster).\
                filter(False == Node.pending_deletion).\
                order_by(Node.id).all()

        return sorted(set(nodes + controller_nodes),
                      key=lambda node: node.id)

    @classmethod
    def set_primary_controller(cls, nodes):
        """Set primary controller for the first controller
        node if it not set yet
        """
        sorted_nodes = sorted(
            nodes, key=lambda node: node['uid'])

        primary_controller = cls.filter_by_roles(
            sorted_nodes, ['primary-controller'])

        if not primary_controller:
            controllers = cls.filter_by_roles(
                sorted_nodes, ['controller'])
            if controllers:
                controllers[0]['role'] = 'primary-controller'

    @classmethod
    def node_list(cls, nodes):
        """Node list
        """
        node_list = super(OrchestratorHASerializer, cls).node_list(nodes)

        for node in node_list:
            node['swift_zone'] = node['uid']

        return node_list

    @classmethod
    def get_common_attrs(cls, cluster):
        """Common attributes for all facts
        """
        common_attrs = super(OrchestratorHASerializer, cls).get_common_attrs(
            cluster)

        netmanager = NetworkManager()
        common_attrs['management_vip'] = netmanager.assign_vip(
            cluster.id, 'management')
        common_attrs['public_vip'] = netmanager.assign_vip(
            cluster.id, 'public')

        sorted_nodes = sorted(
            common_attrs['nodes'], key=lambda node: node['uid'])

        controller_nodes = cls.filter_by_roles(
            sorted_nodes, ['controller', 'primary-controller'])
        common_attrs['last_controller'] = controller_nodes[-1]['name']

        # Assign primary controller in nodes list
        cls.set_primary_controller(common_attrs['nodes'])

        common_attrs['mp'] = [
            {'point': '1', 'weight': '1'},
            {'point': '2', 'weight': '2'}]

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
        for n in cls.not_roles(nodes, 'storage'):
            n['priority'] = storage_prior

        # Controllers deployed one by one
        for n in cls.by_role(nodes, 'primary-controller'):
            n['priority'] = prior.next

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


def serialize(cluster):
    """Serialization depends on deployment mode
    """
    cluster.prepare_for_deployment()

    if cluster.mode == 'multinode':
        serializer = OrchestratorSerializer
    elif cluster.is_ha_mode:
        # Same serializer for all ha
        serializer = OrchestratorHASerializer

    return serializer.serialize(cluster)
