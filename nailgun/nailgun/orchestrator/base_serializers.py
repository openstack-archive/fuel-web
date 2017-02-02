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

from nailgun import objects


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
        test_vm_image['properties']['murano_image_info'] = \
            """'{"title": "Murano Demo", "type": "cirros.demo"}'"""
        return {'test_vm_image': test_vm_image}
