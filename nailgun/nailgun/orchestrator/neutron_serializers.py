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
from ordereddict import OrderedDict
import six

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.logger import logger
from nailgun.objects import Cluster
from nailgun.objects import Node
from nailgun.objects import NodeGroupCollection
from nailgun.orchestrator.base_serializers import NetworkDeploymentSerializer
from nailgun.settings import settings
from nailgun import utils


class NeutronNetworkDeploymentSerializer(NetworkDeploymentSerializer):

    @classmethod
    def network_provider_cluster_attrs(cls, cluster):
        """Cluster attributes."""
        attrs = {'quantum': True,
                 'quantum_settings': cls.neutron_attrs(cluster)}

        if cluster.mode == 'multinode':
            for node in cluster.nodes:
                if cls._node_has_role_by_name(node, 'controller'):
                    net_manager = Cluster.get_network_manager(cluster)
                    networks = net_manager.get_node_networks(node)
                    mgmt_cidr = net_manager.get_network_by_netname(
                        'management', networks)['ip']
                    attrs['management_vip'] = mgmt_cidr.split('/')[0]
                    break

        return attrs

    @classmethod
    def network_provider_node_attrs(cls, cluster, node):
        """Serialize node, then it will be
        merged with common attributes
        """
        nm = Cluster.get_network_manager(cluster)
        networks = nm.get_node_networks(node)
        node_attrs = {
            'network_scheme': cls.generate_network_scheme(node, networks),
        }
        node_attrs = cls.mellanox_settings(node_attrs, cluster, networks)
        return node_attrs

    @classmethod
    def mellanox_settings(cls, node_attrs, cluster, networks):
        """Serialize mellanox node attrs, then it will be
        merged with common attributes, if mellanox plugin or iSER storage
        enabled.
        """
        # Get Mellanox data
        neutron_mellanox_data =  \
            Cluster.get_attributes(cluster).editable\
            .get('neutron_mellanox', {})

        # Get storage data
        storage_data = \
            Cluster.get_attributes(cluster).editable.get('storage', {})

        # Get network manager
        nm = Cluster.get_network_manager(cluster)

        # Init mellanox dict
        node_attrs['neutron_mellanox'] = {}

        # Find Physical port for VFs generation
        if 'plugin' in neutron_mellanox_data and \
           neutron_mellanox_data['plugin']['value'] == 'ethernet':
            node_attrs = cls.set_mellanox_ml2_config(
                node_attrs, nm, networks)

        # Fix network scheme to have physical port for RDMA if iSER enabled
        if 'iser' in storage_data and storage_data['iser']['value']:
            node_attrs = cls.fix_iser_port(node_attrs, nm, networks)

        return node_attrs

    @classmethod
    def set_mellanox_ml2_config(cls, node_attrs, nm, networks):
        """Change the yaml file to include the required configurations
        for ml2 mellanox mechanism driver.
        should be called only in case of mellanox SR-IOV plugin usage.
        """
        # Set physical port for SR-IOV virtual functions
        node_attrs['neutron_mellanox']['physical_port'] = \
            nm.get_network_by_netname('private', networks)['dev']

        # Set ML2 eswitch section conf
        ml2_eswitch = {}
        ml2_eswitch['vnic_type'] = 'hostdev'
        ml2_eswitch['apply_profile_patch'] = True
        node_attrs['neutron_mellanox']['ml2_eswitch'] = ml2_eswitch

        return node_attrs

    @classmethod
    def fix_iser_port(cls, node_attrs, nm, networks):
        """Change the iser port to eth_iser probed (VF on the HV) interface
        instead of br-storage. that change is made due to RDMA
        (Remote Direct Memory Access) limitation of working with physical
        interfaces.
        """
        # Set a new unique name for iSER virtual port
        iser_new_name = 'eth_iser0'

        # Add iSER extra params to astute.yaml
        node_attrs['neutron_mellanox']['storage_parent'] = \
            nm.get_network_by_netname('storage', networks)['dev']
        node_attrs['neutron_mellanox']['iser_interface_name'] = iser_new_name

        # Get VLAN if exists
        storage_vlan = \
            nm.get_network_by_netname('storage', networks).get('vlan')

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

        if Node.should_have_public(node):
            attrs['endpoints']['br-ex'] = {}
            attrs['roles']['ex'] = 'br-ex'

        nm = Cluster.get_network_manager(node.cluster)
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
        if not Node.should_have_public(node):
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
        if Node.should_have_public(node):
            netgroup_mapping.append(('public', 'br-ex'))

        netgroups = {}
        for ngname, brname in netgroup_mapping:
            # Here we get a dict with network description for this particular
            # node with its assigned IPs and device names for each network.
            netgroup = nm.get_network_by_netname(ngname, networks)
            if netgroup.get('ip'):
                attrs['endpoints'][brname]['IP'] = [netgroup['ip']]
            netgroups[ngname] = netgroup

        if Node.should_have_public(node):
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
                    'br-%s' % nm.get_node_interface_by_netname(
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
            "tenant": Cluster.get_creds(cluster)['tenant']['value'],
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
            "tenant": Cluster.get_creds(cluster)['tenant']['value'],
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
    def generate_network_scheme(cls, node, networks):
        attrs = super(NeutronNetworkDeploymentSerializer60, cls). \
            generate_network_scheme(node, networks)

        for item in attrs.get('transformations', ()):
            if 'tags' in item:
                item['vlan_ids'] = item['tags']

        # Include information about all subnets that don't belong to this node.
        # This is used during deployment to configure routes to all other
        # networks in the environment.
        nm = Cluster.get_network_manager(node.cluster)
        other_nets = nm.get_networks_not_on_node(node, networks)

        netgroup_mapping = [
            ('storage', 'br-storage'),
            ('management', 'br-mgmt'),
            ('fuelweb_admin', 'br-fw-admin'),
        ]
        if Node.should_have_public(node):
            netgroup_mapping.append(('public', 'br-ex'))

        for ngname, brname in netgroup_mapping:
            netgroup = nm.get_network_by_netname(ngname, networks)
            if netgroup.get('gateway'):
                attrs['endpoints'][brname]['gateway'] = netgroup['gateway']
            attrs['endpoints'][brname]['other_nets'] = \
                other_nets.get(ngname, [])

        if Node.should_have_public(node):
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

        is_public = Node.should_have_public(node)
        if is_public:
            attrs['endpoints']['br-ex'] = {'IP': 'none'}
            attrs['endpoints']['br-floating'] = {'IP': 'none'}
            attrs['roles']['ex'] = 'br-ex'
            attrs['roles']['neutron/floating'] = 'br-floating'

        nm = Cluster.get_network_manager(node.cluster)

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

        if NodeGroupCollection.get_by_cluster_id(
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

    @classmethod
    def get_default_network_to_endpoint_mapping(cls, node):
        mapping = {
            consts.NETWORKS.fuelweb_admin: 'br-fw-admin',
            consts.NETWORKS.storage: 'br-storage',
            consts.NETWORKS.management: 'br-mgmt',
            consts.NETWORKS.private: 'br-prv'}

        # roles can be assigned to br-ex only in case it has a public IP
        if Node.should_have_public_with_ip(node):
            mapping[consts.NETWORKS.public] = 'br-ex'

        return mapping

    @classmethod
    def get_network_to_ip_mapping(cls, node):
        nm = Cluster.get_network_manager(node.cluster)

        mapping = dict()
        networks = nm.get_node_networks(node)
        for net in cls.get_default_network_to_endpoint_mapping(node):
            netgroup = nm.get_network_by_netname(net, networks)
            if netgroup.get('ip'):
                mapping[net] = netgroup['ip'].split('/')[0]

        return mapping

    @classmethod
    def _get_network_role_mapping(cls, node, mapping):
        """Aggregates common logic for methods 'get_network_role_mapping_to_ip'
        and 'get_network_role_mapping_to_interfaces'.
        """
        roles = dict()
        for role in Cluster.get_network_roles(node.cluster):
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
        mapping = cls.get_default_network_to_endpoint_mapping(node)
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
    def generate_network_scheme(cls, node, networks):
        attrs = super(NeutronNetworkDeploymentSerializer70,
                      cls).generate_network_scheme(node, networks)

        mapping = cls.get_network_role_mapping_to_interfaces(node)

        old_mapping_6_1 = attrs['roles']
        mapping.update(old_mapping_6_1)
        attrs['roles'] = mapping

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
        nm = Cluster.get_network_manager(cluster)

        for node in Cluster.get_nodes_not_for_deletion(cluster):
            name = Node.get_slave_name(node)
            node_roles = Node.all_roles(node)
            network_roles = cls.get_network_role_mapping_to_ip(node)

            nodes[name] = {
                "uid": node.uid,
                "fqdn": Node.get_node_fqdn(node),
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
        """Returns network roles for the specified node based
        on the node's assigned roles.
        """
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
        """Overrides default transformation generation.
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
        for role in roles:
            for t in template['templates_for_node_role'][role]:
                role_templates[t] = True

        for t in role_templates:
            txs.extend(template['templates'][t]['transformations'])

        return txs

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

        nm = Cluster.get_network_manager(node.cluster)

        netgroups = nm.get_node_networks_with_ips(node)
        netgroup_mapping = nm.get_node_network_mapping(node)
        for ngname, brname in netgroup_mapping:
            ip_addr = netgroups.get(ngname, {}).get('ip')
            if ip_addr:
                attrs['endpoints'][brname] = {'IP': [ip_addr]}
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

        if NodeGroupCollection.get_by_cluster_id(
                node.cluster.id).count() > 1:
            cls.generate_routes(node, attrs, nm, netgroup_mapping, netgroups,
                                networks)

        attrs = cls.generate_driver_information(node, attrs, nm, networks)

        return attrs

    @classmethod
    def _get_endpoint_to_ip_mapping(cls, node):
        nm = Cluster.get_network_manager(node.cluster)
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
        nm = Cluster.get_network_manager(cluster)
        for node in Cluster.get_nodes_not_for_deletion(cluster):
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
