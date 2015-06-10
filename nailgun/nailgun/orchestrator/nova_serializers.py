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

"""Nova network deployment serializers for orchestrator"""

from collections import defaultdict
from netaddr import IPNetwork

from nailgun import consts
from nailgun.objects import Cluster
from nailgun.orchestrator.base_serializers import NetworkDeploymentSerializer


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
        net_manager = Cluster.get_network_manager(node.cluster)
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


class NovaNetworkDeploymentSerializer61(NovaNetworkDeploymentSerializer):

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

        nm = Cluster.get_network_manager(node.cluster)

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
