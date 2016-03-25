# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

from distutils.version import StrictVersion

from nailgun import consts
from nailgun.errors import errors

from nailgun.extensions.network_manager.managers import default
from nailgun.extensions.network_manager.managers import neutron
from nailgun.extensions.network_manager.managers import nova_network


class NetworkManager(object):
    def __init__(self, cluster=None):
        if cluster is None:
            self.impl = default.DefaultNetworkManager
        else:
            ver = cluster.release.environment_version
            net_provider = cluster.net_provider
            if net_provider == consts.CLUSTER_NET_PROVIDERS.neutron:
                if StrictVersion(ver) < StrictVersion('6.1'):
                    self.impl = neutron.NeutronManagerLegacy
                elif StrictVersion(ver) == StrictVersion('6.1'):
                    self.impl = neutron.NeutronManager61
                elif StrictVersion(ver) == StrictVersion('7.0'):
                    self.impl = neutron.NeutronManager70
                elif StrictVersion(ver) >= StrictVersion('8.0'):
                    self.impl = neutron.NeutronManager80
                else:
                    self.impl = neutron.NeutronManager
            elif net_provider == consts.CLUSTER_NET_PROVIDERS.nova_network:
                if StrictVersion(ver) < StrictVersion('6.1'):
                    self.impl = nova_network.NovaNetworkManagerLegacy
                elif StrictVersion(ver) == StrictVersion('6.1'):
                    self.impl = nova_network.NovaNetworkManager61
                elif StrictVersion(ver) == StrictVersion('7.0'):
                    self.impl = nova_network.NovaNetworkManager70
                elif StrictVersion(ver) >= StrictVersion('8.0'):
                    raise errors.NovaNetworkNotSupported()
                else:
                    self.impl = nova_network.NovaNetworkManager
            else:
                raise ValueError(
                    'The network provider "{0}" is not supported.'
                    .format(net_provider)
                )

    def assign_given_vips_for_net_groups(self, *args, **kwargs):
        return self.impl.assign_given_vips_for_net_groups(*args, **kwargs)

    def assign_networks_by_default(self, *args, **kwargs):
        return self.impl.assign_networks_by_default(*args, **kwargs)

    def assign_networks_by_template(self, *args, **kwargs):
        return self.impl.assign_networks_by_template(*args, **kwargs)

    def assign_vips_for_net_groups(self, *args, **kwargs):
        return self.impl.assign_vips_for_net_groups(*args, **kwargs)

    def assign_vips_for_net_groups_for_api(self, *args, **kwargs):
        return self.impl.assign_vips_for_net_groups_for_api(*args, **kwargs)

    def check_ips_belong_to_ranges(self, *args, **kwargs):
        return self.impl.check_ips_belong_to_ranges(*args, **kwargs)

    def clear_assigned_networks(self, *args, **kwargs):
        return self.impl.clear_assigned_networks(*args, **kwargs)

    def clear_bond_configuration(self, *args, **kwargs):
        return self.impl.clear_bond_configuration(*args, **kwargs)

    def create_admin_network_group(self, *args, **kwargs):
        return self.impl.create_admin_network_group(*args, **kwargs)

    def create_network_groups(self, *args, **kwargs):
        return self.impl.create_network_groups(*args, **kwargs)

    def create_network_groups_and_config(self, *args, **kwargs):
        return self.impl.create_network_groups_and_config(*args, **kwargs)

    def ensure_gateways_present_in_default_node_group(self, *args, **kwargs):
        return self.impl.ensure_gateways_present_in_default_node_group(
            *args, **kwargs)

    def find_nic_assoc_with_ng(self, *args, **kwargs):
        return self.impl.find_nic_assoc_with_ng(*args, **kwargs)

    def generate_vlan_ids_list(self, *args, **kwargs):
        return self.impl.generate_vlan_ids_list(*args, **kwargs)

    def get_admin_interface(self, *args, **kwargs):
        return self.impl.get_admin_interface(*args, **kwargs)

    def get_admin_ip_for_node(self, *args, **kwargs):
        return self.impl.get_admin_ip_for_node(*args, **kwargs)

    def get_admin_networks(self, *args, **kwargs):
        return self.impl.get_admin_networks(*args, **kwargs)

    def get_assigned_ips_by_network_id(self, *args, **kwargs):
        return self.impl.get_assigned_ips_by_network_id(*args, **kwargs)

    def get_assigned_vips(self, *args, **kwargs):
        return self.impl.get_assigned_vips(*args, **kwargs)

    def get_free_ips(self, *args, **kwargs):
        return self.impl.get_free_ips(*args, **kwargs)

    def get_iface_properties(self, *args, **kwargs):
        return self.impl.get_iface_properties(*args, **kwargs)

    def _get_interface_by_network_name(self, *args, **kwargs):
        return self.impl._get_interface_by_network_name(*args, **kwargs)

    def get_ip_by_network_name(self, *args, **kwargs):
        return self.impl.get_ip_by_network_name(*args, **kwargs)

    def get_lnx_bond_properties(self, *args, **kwargs):
        return self.impl.get_lnx_bond_properties(*args, **kwargs)

    def get_network_config_create_data(self, *args, **kwargs):
        return self.impl.get_network_config_create_data(*args, **kwargs)

    def get_network_by_netname(self, *args, **kwargs):
        return self.impl.get_network_by_netname(*args, **kwargs)

    def get_networks_not_on_node(self, *args, **kwargs):
        return self.impl.get_networks_not_on_node(*args, **kwargs)

    def get_node_groups_info(self, *args, **kwargs):
        return self.impl.get_node_groups_info(*args, **kwargs)

    def get_node_network_mapping(self, *args, **kwargs):
        return self.impl.get_node_network_mapping(*args, **kwargs)

    def get_node_networks(self, *args, **kwargs):
        return self.impl.get_node_networks(*args, **kwargs)

    def get_node_networks_with_ips(self, *args, **kwargs):
        return self.impl.get_node_networks_with_ips(*args, **kwargs)

    def get_ovs_bond_properties(self, *args, **kwargs):
        return self.impl.get_ovs_bond_properties(*args, **kwargs)

    def get_prohibited_admin_bond_modes(self, *args, **kwargs):
        return self.impl.get_prohibited_admin_bond_modes(*args, **kwargs)

    def _get_pxe_iface_name(self, *args, **kwargs):
        return self.impl._get_pxe_iface_name(*args, **kwargs)

    def get_zabbix_url(self, *args, **kwargs):
        return self.impl.get_zabbix_url(*args, **kwargs)

    def is_cidr_intersection(self, *args, **kwargs):
        return self.impl.is_cidr_intersection(*args, **kwargs)

    def is_range_intersection(self, *args, **kwargs):
        return self.impl.is_range_intersection(*args, **kwargs)

    def is_same_network(self, *args, **kwargs):
        return self.impl.is_same_network(*args, **kwargs)

    def prepare_for_deployment(self, *args, **kwargs):
        return self.impl.prepare_for_deployment(*args, **kwargs)

    def prepare_for_provisioning(self, *args, **kwargs):
        return self.impl.prepare_for_provisioning(*args, **kwargs)

    def _update_attrs(self, *args, **kwargs):
        return self.impl._update_attrs(*args, **kwargs)

    def update_interfaces_info(self, *args, **kwargs):
        return self.impl.update_interfaces_info(*args, **kwargs)

    def update_restricted_networks(self, *args, **kwargs):
        return self.impl.update_restricted_networks(*args, **kwargs)

    def update(self, *args, **kwargs):
        return self.impl.update(*args, **kwargs)
