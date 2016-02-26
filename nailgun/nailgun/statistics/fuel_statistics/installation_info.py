#    Copyright 2014 Mirantis, Inc.
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

import copy
import subprocess

from nailgun import consts
from nailgun.db.sqlalchemy.models import NeutronConfig
from nailgun.db.sqlalchemy.models import NovaNetworkConfig
from nailgun.logger import logger
from nailgun.objects import Cluster
from nailgun.objects import ClusterCollection
from nailgun.objects import MasterNodeSettings
from nailgun.objects import NodeCollection
from nailgun.objects.plugin import ClusterPlugins
from nailgun.settings import settings
from nailgun.statistics.utils import get_attr_value
from nailgun.statistics.utils import WhiteListRule


class InstallationInfo(object):
    """Collects info about Fuel installation

    Includes master nodes, clusters, networks, etc.
    Used for collecting info for fuel statistics
    """

    attributes_white_list = (
        # ((path, to, property), 'map_to_name', transform_function)
        WhiteListRule(('common', 'libvirt_type', 'value'),
                      'libvirt_type', None),
        WhiteListRule(('common', 'debug', 'value'), 'debug_mode', None),
        WhiteListRule(('common', 'use_cow_images', 'value'),
                      'use_cow_images', None),
        WhiteListRule(('common', 'auto_assign_floating_ip', 'value'),
                      'auto_assign_floating_ip', None),
        WhiteListRule(('common', 'nova_quota', 'value'), 'nova_quota', None),
        WhiteListRule(('common', 'puppet_debug', 'value'),
                      'puppet_debug', None),
        WhiteListRule(('common', 'resume_guests_state_on_host_boot', 'value'),
                      'resume_guests_state_on_host_boot', None),
        WhiteListRule(('common', 'task_deploy', 'value'),
                      'task_deploy', None),
        WhiteListRule(('corosync', 'verified', 'value'),
                      'corosync_verified', None),

        WhiteListRule(('public_network_assignment', 'assign_to_all_nodes',
                       'value'), 'assign_public_to_all_nodes', None),
        WhiteListRule(('neutron_advanced_configuration', 'neutron_l2_pop',
                       'value'), 'neutron_l2_pop', None),
        WhiteListRule(('neutron_advanced_configuration', 'neutron_dvr',
                       'value'), 'neutron_dvr', None),
        WhiteListRule(('neutron_advanced_configuration', 'neutron_l3_ha',
                       'value'), 'neutron_l3_ha', None),
        WhiteListRule(('syslog', 'syslog_transport', 'value'),
                      'syslog_transport', None),
        WhiteListRule(('provision', 'method', 'value'),
                      'provision_method', None),
        WhiteListRule(('kernel_params', 'kernel', 'value'),
                      'kernel_params', None),

        WhiteListRule(('external_mongo', 'mongo_replset', 'value'),
                      'external_mongo_replset', bool),
        WhiteListRule(('external_ntp', 'ntp_list', 'value'),
                      'external_ntp_list', bool),

        WhiteListRule(('repo_setup', 'repos', 'value'), 'repos', bool),

        WhiteListRule(('storage', 'volumes_lvm', 'value'),
                      'volumes_lvm', None),
        WhiteListRule(('storage', 'iser', 'value'), 'iser', None),
        WhiteListRule(('storage', 'volumes_block_device', 'value'),
                      'volumes_block_device', None),
        WhiteListRule(('storage', 'volumes_ceph', 'value'),
                      'volumes_ceph', None),
        WhiteListRule(('storage', 'images_ceph', 'value'),
                      'images_ceph', None),
        WhiteListRule(('storage', 'images_vcenter', 'value'),
                      'images_vcenter', None),
        WhiteListRule(('storage', 'ephemeral_ceph', 'value'),
                      'ephemeral_ceph', None),
        WhiteListRule(('storage', 'objects_ceph', 'value'),
                      'objects_ceph', None),
        WhiteListRule(('storage', 'osd_pool_size', 'value'),
                      'osd_pool_size', None),

        WhiteListRule(('neutron_mellanox', 'plugin', 'value'),
                      'mellanox', None),
        WhiteListRule(('neutron_mellanox', 'vf_num', 'value'),
                      'mellanox_vf_num', None),

        WhiteListRule(('additional_components', 'sahara', 'value'),
                      'sahara', None),
        WhiteListRule(('additional_components', 'murano', 'value'),
                      'murano', None),
        WhiteListRule(('additional_components', 'murano-cfapi', 'value'),
                      'murano-cfapi', None),
        WhiteListRule(('additional_components',
                       'murano_glance_artifacts_plugin', 'value'),
                      'murano_glance_artifacts_plugin', None),
        WhiteListRule(('additional_components', 'heat', 'value'),
                      'heat', None),
        WhiteListRule(('additional_components', 'ceilometer', 'value'),
                      'ceilometer', None),
        WhiteListRule(('additional_components', 'mongo', 'value'),
                      'mongo', None),
        WhiteListRule(('additional_components', 'ironic', 'value'),
                      'ironic', None),

        WhiteListRule(('workloads_collector', 'enabled', 'value'),
                      'workloads_collector_enabled', None),

        WhiteListRule(('public_ssl', 'horizon', 'value'),
                      'public_ssl_horizon', None),
        WhiteListRule(('public_ssl', 'services', 'value'),
                      'public_ssl_services', None),
        WhiteListRule(('public_ssl', 'cert_source', 'value'),
                      'public_ssl_cert_source', None),
    )

    vmware_attributes_white_list = (
        # ((path, to, property), 'map_to_name', transform_function)
        WhiteListRule(('value', 'availability_zones', 'cinder', 'enable'),
                      'vmware_az_cinder_enable', None),
        # We add 'vsphere_cluster' into path for enter into nested list.
        # Private value of 'vsphere_cluster' is not collected, we only
        # computes length of the nested list
        WhiteListRule(('value', 'availability_zones', 'nova_computes',
                       'vsphere_cluster'), 'vmware_az_nova_computes_num', len),
    )

    plugin_info_white_list = (
        # ((path, to, property), 'map_to_name', transform_function)
        WhiteListRule(('id',), 'id', None),
        WhiteListRule(('name',), 'name', None),
        WhiteListRule(('version',), 'version', None),
        WhiteListRule(('releases',), 'releases', None),
        WhiteListRule(('fuel_version',), 'fuel_version', None),
        WhiteListRule(('package_version',), 'package_version', None),
        WhiteListRule(('groups',), 'groups', None),
        WhiteListRule(('licenses',), 'licenses', None),
        WhiteListRule(('is_hotpluggable',), 'is_hotpluggable', None),
        WhiteListRule(('attributes_metadata',), 'attributes_metadata', None),
        WhiteListRule(('volumes_metadata',), 'volumes_metadata', None),
        WhiteListRule(('roles_metadata',), 'roles_metadata', None),
        WhiteListRule(('network_roles_metadata',),
                      'network_roles_metadata', None),
        WhiteListRule(('components_metadata',), 'components_metadata', None),
        WhiteListRule(
            ('nic_attributes_metadata',), 'nic_attributes_metadata', None),
        WhiteListRule(
            ('bond_attributes_metadata',), 'bond_attributes_metadata', None),
        WhiteListRule(
            ('node_attributes_metadata',), 'node_attributes_metadata', None),
        WhiteListRule(('deployment_tasks',), 'deployment_tasks', None),
        WhiteListRule(('tasks',), 'tasks', None),
    )

    def fuel_release_info(self):
        return settings.VERSION

    def fuel_packages_info(self):
        command = ['rpm', '-q']
        command.extend(consts.STAT_FUEL_PACKAGES)
        p = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.poll() != 0:
            logger.error("Command '%s' failed. Error: %s",
                         " ".join(command), err)
            return []
        return out.strip().split()

    def get_network_configuration_info(self, cluster):
        network_config = cluster.network_config
        result = {}
        if isinstance(network_config, NovaNetworkConfig):
            result['net_manager'] = network_config.net_manager
            result['fixed_networks_vlan_start'] = \
                network_config.fixed_networks_vlan_start
            result['fixed_network_size'] = network_config.fixed_network_size
            result['fixed_networks_amount'] = \
                network_config.fixed_networks_amount
        elif isinstance(network_config, NeutronConfig):
            result['segmentation_type'] = network_config.segmentation_type
            result['net_l23_provider'] = network_config.net_l23_provider
        return result

    def get_clusters_info(self):
        clusters = ClusterCollection.all()
        clusters_info = []
        for cluster in clusters:
            release = cluster.release
            nodes_num = NodeCollection.filter_by(
                None, cluster_id=cluster.id).count()
            vmware_attributes_editable = None
            if cluster.vmware_attributes:
                vmware_attributes_editable = cluster.vmware_attributes.editable
            cluster_info = {
                'id': cluster.id,
                'nodes_num': nodes_num,
                'release': {
                    'os': release.operating_system,
                    'name': release.name,
                    'version': release.version
                },
                'mode': cluster.mode,
                'nodes': self.get_nodes_info(cluster.nodes),
                'node_groups': self.get_node_groups_info(cluster.node_groups),
                'status': cluster.status,
                'extensions': cluster.extensions,
                'attributes': self.get_attributes(
                    Cluster.get_editable_attributes(cluster),
                    self.attributes_white_list
                ),
                'vmware_attributes': self.get_attributes(
                    vmware_attributes_editable,
                    self.vmware_attributes_white_list
                ),
                'plugin_links': self.get_plugin_links(
                    cluster.plugin_links),
                'net_provider': cluster.net_provider,
                'fuel_version': cluster.fuel_version,
                'is_customized': cluster.is_customized,
                'network_configuration': self.get_network_configuration_info(
                    cluster),
                'installed_plugins': self.get_cluster_plugins_info(cluster),
                'components': cluster.components
            }
            clusters_info.append(cluster_info)
        return clusters_info

    def get_cluster_plugins_info(self, cluster):
        plugins_info = []
        for plugin_inst in ClusterPlugins.get_enabled(cluster.id):
            plugin_info = self.get_attributes(plugin_inst.__dict__,
                                              self.plugin_info_white_list)
            plugins_info.append(plugin_info)

        return plugins_info

    def get_attributes(self, attributes, white_list):
        result_attrs = {}
        for path, map_to_name, func in white_list:
            try:
                result_attrs[map_to_name] = get_attr_value(
                    path, func, attributes)
            except (KeyError, TypeError):
                pass
        return result_attrs

    def get_node_meta(self, node):
        meta = copy.deepcopy(node.meta)
        result = {}

        if not meta:
            return result

        to_copy = ['cpu', 'memory', 'disks']
        for param in to_copy:
            result[param] = meta.get(param)

        system = meta.get('system', {})
        system.pop('fqdn', None)
        system.pop('serial', None)
        result['system'] = system

        interfaces = meta.get('interfaces', [])
        result['interfaces'] = []
        for interface in interfaces:
            interface.pop('mac')
            result['interfaces'].append(interface)

        return result

    def get_nodes_info(self, nodes):
        nodes_info = []
        for node in nodes:
            node_info = {
                'id': node.id,
                'group_id': node.group_id,
                'roles': node.roles,
                'os': node.os_platform,

                'status': node.status,
                'error_type': node.error_type,
                'online': node.online,

                'manufacturer': node.manufacturer,
                'platform_name': node.platform_name,
                'meta': self.get_node_meta(node),

                'pending_addition': node.pending_addition,
                'pending_deletion': node.pending_deletion,
                'pending_roles': node.pending_roles,

                'nic_interfaces':
                self.get_node_intefaces_info(node.nic_interfaces, bond=False),
                'bond_interfaces':
                self.get_node_intefaces_info(node.bond_interfaces, bond=True),
            }
            nodes_info.append(node_info)
        return nodes_info

    def get_node_intefaces_info(self, interfaces, bond):
        ifs_info = []
        for interface in interfaces:
            if_info = {
                'id': interface.id
            }
            if bond:
                if_info['slaves'] = [s.id for s in interface.slaves]
            ifs_info.append(if_info)
        return ifs_info

    def get_node_groups_info(self, node_groups):
        groups_info = []
        for group in node_groups:
            group_info = {
                'id': group.id,
                'nodes': [n.id for n in group.nodes]
            }
            groups_info.append(group_info)
        return groups_info

    def get_plugin_links(self, plugin_links):
        return [{'id': e.id, 'title': e.title, 'description': e.description,
                 'hidden': e.hidden} for e in plugin_links]

    def get_installation_info(self):
        clusters_info = self.get_clusters_info()
        allocated_nodes_num = sum([c['nodes_num'] for c in clusters_info])
        unallocated_nodes_num = NodeCollection.filter_by(
            None, cluster_id=None).count()

        info = {
            'user_information': self.get_user_info(),
            'master_node_uid': self.get_master_node_uid(),
            'fuel_release': self.fuel_release_info(),
            'fuel_packages': self.fuel_packages_info(),
            'clusters': clusters_info,
            'clusters_num': len(clusters_info),
            'allocated_nodes_num': allocated_nodes_num,
            'unallocated_nodes_num': unallocated_nodes_num
        }

        return info

    def get_master_node_uid(self):
        return getattr(MasterNodeSettings.get_one(), 'master_node_uid', None)

    def get_user_info(self):
        try:
            stat_settings = MasterNodeSettings.get_one(). \
                settings.get("statistics", {})
            result = {
                "contact_info_provided":
                stat_settings.get("user_choice_saved", {}).get("value", False)
                and stat_settings.get("send_user_info", {}).get("value", False)
            }
            if result["contact_info_provided"]:
                result["name"] = stat_settings.get("name", {}).get("value")
                result["email"] = stat_settings.get("email", {}).get("value")
                result["company"] = stat_settings.get("company", {}).\
                    get("value")
            return result
        except AttributeError:
            return {"contact_info_provided": False}
