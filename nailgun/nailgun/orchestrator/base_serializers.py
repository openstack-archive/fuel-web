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

"""Base classes of deployment serializers for orchestrator"""

from copy import deepcopy
from netaddr import IPNetwork

from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.errors import errors
from nailgun import objects
from nailgun.settings import settings


class MellanoxMixin(object):

    @classmethod
    def inject_mellanox_settings_for_deployment(
            cls, node_attrs, cluster, networks):
        """Mellanox settings for deployment

        Serialize mellanox node attrs then it will be merged with common
        attributes, if mellanox plugin or iSER storage enabled.

        :param node_attrs: attributes for specific node
        :type node_attrs: dict
        :param cluster: A cluster instance
        :type cluster: Cluster model
        :param networks: networks related for specific node
        :type networks: list
        :returns: None
        """

        cluster_attrs = objects.Cluster.get_editable_attributes(cluster)
        neutron_mellanox_data = cluster_attrs.get('neutron_mellanox', {})
        # We need to support mellanox for releases < 8.0. So if mellanox
        # attributes exist (primary in old releases) then merge them with
        # common node attributes.
        if neutron_mellanox_data:
            storage_data = cluster_attrs.get('storage', {})
            nm = objects.Cluster.get_network_manager(cluster)
            node_attrs['neutron_mellanox'] = {}

            # Find Physical port for VFs generation
            if 'plugin' in neutron_mellanox_data and \
                    neutron_mellanox_data['plugin']['value'] == 'ethernet':
                # Set config for ml2 mellanox mechanism driver
                node_attrs['neutron_mellanox'].update({
                    'physical_port': nm.get_network_by_netname(
                        'private', networks)['dev'],
                    'ml2_eswitch': {
                        'vnic_type': 'hostdev',
                        'apply_profile_patch': True}
                })

            # Fix network scheme to have physical port for RDMA if iSER enabled
            if 'iser' in storage_data and storage_data['iser']['value']:
                iser_new_name = 'eth_iser0'
                node_attrs['neutron_mellanox'].update({
                    'storage_parent': nm.get_network_by_netname(
                        'storage', networks)['dev'],
                    'iser_interface_name': iser_new_name
                })

                storage_vlan = \
                    nm.get_network_by_netname('storage', networks).get('vlan')
                if storage_vlan:
                    vlan_name = "vlan{0}".format(storage_vlan)
                    # Set storage rule to iSER interface vlan interface
                    node_attrs['network_scheme']['roles']['storage'] = \
                        vlan_name
                    # Set iSER interface vlan interface
                    node_attrs['network_scheme']['interfaces'][vlan_name] = \
                        {'L2': {'vlan_splinters': 'off'}}
                    node_attrs['network_scheme']['endpoints'][vlan_name] = \
                        node_attrs['network_scheme']['endpoints'].pop(
                            'br-storage', {})
                    node_attrs['network_scheme']['endpoints'][vlan_name][
                        'vlandev'] = iser_new_name
                else:
                    # Set storage rule to iSER port
                    node_attrs['network_scheme']['roles'][
                        'storage'] = iser_new_name
                    node_attrs['network_scheme']['interfaces'][
                        iser_new_name] = {'L2': {'vlan_splinters': 'off'}}
                    node_attrs['network_scheme']['endpoints'][
                        iser_new_name] = node_attrs['network_scheme'][
                        'endpoints'].pop('br-storage', {})

    @classmethod
    def inject_mellanox_settings_for_provisioning(
            cls, cluster_attrs, serialized_node):
        """Mellanox settings for provisioning

        Serialize mellanox node attrs then it will be merged with common
        node attributes

        :param cluster_attrs: cluster attributes
        :type cluster_attrs: dict
        :param serialized_node: node attributes data for provisioning
        :type serialized_node: dict
        :returns: None
        """
        mellanox_data = cluster_attrs.get('neutron_mellanox')
        # We need to support mellanox for releases < 8.0. So if mellanox
        # attributes exist (primary in old releases) then merge them with
        # common node attributes.
        if mellanox_data:
            serialized_node['ks_meta'].update({
                'mlnx_vf_num': mellanox_data.get('vf_num'),
                'mlnx_plugin_mode': mellanox_data.get('plugin'),
                'mlnx_iser_enabled': cluster_attrs.get(
                    'storage', {}).get('iser')
            })
            # Add relevant kernel parameter when using Mellanox SR-IOV
            # and/or iSER (which works on top of a probed virtual function)
            # unless it was explicitly added by the user
            pm_data = serialized_node['ks_meta']['pm_data']
            if ((mellanox_data['plugin'] == 'ethernet' or
                    cluster_attrs['storage']['iser'] is True) and
                    'intel_iommu=' not in pm_data['kernel_params']):
                        pm_data['kernel_params'] += ' intel_iommu=on'


class MuranoMetadataSerializerMixin(object):

    def generate_test_vm_image_data(self, node):
        return self.inject_murano_settings(super(
            MuranoMetadataSerializerMixin,
            self).generate_test_vm_image_data(node))

    def inject_murano_settings(self, image_data):
        """Adds murano metadata to the test image"""
        test_vm_image = image_data['test_vm_image']
        existing_properties = test_vm_image['glance_properties']
        murano_data = ' '.join(["""--property murano_image_info='{"title":"""
                               """ "Murano Demo", "type": "cirros.demo"}'"""])
        test_vm_image['glance_properties'] = existing_properties + murano_data
        return {'test_vm_image': test_vm_image}


class VmwareDeploymentSerializerMixin(object):

    def generate_vmware_data(self, node):
        """Extend serialize data with vmware attributes"""
        vmware_data = {}
        allowed_roles = [
            'controller',
            'primary-controller',
            'compute-vmware',
            'cinder-vmware'
        ]

        all_roles = objects.Node.all_roles(node)
        use_vcenter = node.cluster.attributes.editable.get('common', {}) \
            .get('use_vcenter', {}).get('value')

        if (use_vcenter and any(role in allowed_roles for role in all_roles)):
            compute_instances = []
            cinder_instances = []

            vmware_attributes = node.cluster.vmware_attributes.editable \
                .get('value', {})
            availability_zones = vmware_attributes \
                .get('availability_zones', {})
            glance_instance = vmware_attributes.get('glance', {})
            network = vmware_attributes.get('network', {})

            for zone in availability_zones:

                vc_user = self.escape_dollar(zone.get('vcenter_username', ''))
                vc_password = self.escape_dollar(zone.get('vcenter_password',
                                                          ''))

                for compute in zone.get('nova_computes', {}):
                    datastore_regex = \
                        self.escape_dollar(compute.get('datastore_regex', ''))

                    compute_item = {
                        'availability_zone_name': zone.get('az_name', ''),
                        'vc_host': zone.get('vcenter_host', ''),
                        'vc_user': vc_user,
                        'vc_password': vc_password,
                        'service_name': compute.get('service_name', ''),
                        'vc_cluster': compute.get('vsphere_cluster', ''),
                        'datastore_regex': datastore_regex,
                        'target_node': compute.get('target_node', {}).get(
                            'current', {}).get('id', 'controllers')
                    }

                    compute_instances.append(compute_item)

                cinder_item = {
                    'availability_zone_name': zone.get('az_name', ''),
                    'vc_host': zone.get('vcenter_host', ''),
                    'vc_user': vc_user,
                    'vc_password': vc_password
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
                glance_username = \
                    self.escape_dollar(glance_instance
                                       .get('vcenter_username', ''))
                glance_password = \
                    self.escape_dollar(glance_instance
                                       .get('vcenter_password', ''))

                vmware_data['glance'] = {
                    'vc_host': glance_instance.get('vcenter_host', ''),
                    'vc_user': glance_username,
                    'vc_password': glance_password,
                    'vc_datacenter': glance_instance.get('datacenter', ''),
                    'vc_datastore': glance_instance.get('datastore', '')
                }

        return vmware_data

    @staticmethod
    def escape_dollar(data):
        """Escape dollar symbol

        In order to disable variable interpolation in
        values that we write to configuration files during
        deployment we must replace all $ (dollar sign) occurrences.
        """
        return data.replace('$', '$$')


class NetworkDeploymentSerializer(object):

    @classmethod
    def update_nodes_net_info(cls, cluster, nodes):
        """Adds information about networks to each node."""
        default_admin_net = objects.NetworkGroup.get_default_admin_network()

        nm = objects.Cluster.get_network_manager(cluster)
        for node in objects.Cluster.get_nodes_not_for_deletion(cluster):
            netw_data = nm.get_node_networks(node, default_admin_net)
            addresses = {}
            for net in node.cluster.network_groups:
                if net.name == 'public' and \
                        not objects.Node.should_have_public_with_ip(node):
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
            cls.network_ranges(objects.Cluster.get_default_group(cluster).id))
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
        """Get all ip ranges in "10.0.0.0-10.0.0.255" format"""
        return [
            "{0}-{1}".format(ip_range.first, ip_range.last)
            for ip_range in network_group.ip_ranges
        ]

    @classmethod
    def get_addr_mask(cls, network_data, net_name, render_name):
        """Get addr for network by name"""
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
        network_manager = objects.Cluster.get_network_manager(node.cluster)
        admin_ip = network_manager.get_admin_ip_for_node(node)
        admin_ip = IPNetwork(admin_ip)

        # Assign prefix from admin network
        admin_net = IPNetwork(
            objects.NetworkGroup.get_admin_network_group(node).cidr
        )
        admin_ip.prefixlen = admin_net.prefixlen

        return str(admin_ip)

    @classmethod
    def add_bridge(cls, name, provider=None, vendor_specific=None):
        """Add bridge to schema

        It will take global provider if it is omitted here
        """
        bridge = {
            'action': 'add-br',
            'name': name
        }
        if provider:
            bridge['provider'] = provider
        if vendor_specific:
            bridge['vendor_specific'] = vendor_specific
        return bridge

    @classmethod
    def add_port(cls, name, bridge, provider=None, vendor_specific=None):
        """Add port to schema

        Bridge name may be None, port will not be connected to any bridge then
        It will take global provider if it is omitted here
        Port name can be in form "XX" or "XX.YY", where XX - NIC name,
        YY - vlan id. E.g. "eth0", "eth0.1021". This will create corresponding
        interface if name includes vlan id.

        :param name: (sub)interface name, string
        :param bridge: bridge name, nullable string
        :param provider: provider name, nullable string
        :param vendor_specific: vendor specific parameters, dict
        :return: add-port transformation, dict
        """
        port = {
            'action': 'add-port',
            'name': name
        }
        if bridge:
            port['bridge'] = bridge
        if provider:
            port['provider'] = provider
        if vendor_specific:
            port['vendor_specific'] = vendor_specific
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
