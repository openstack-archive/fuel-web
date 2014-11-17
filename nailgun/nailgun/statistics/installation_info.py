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


from nailgun.objects import ClusterCollection
from nailgun.objects import MasterNodeSettings
from nailgun.objects import NodeCollection
from nailgun.settings import settings
from nailgun import utils


class InstallationInfo(object):
    """Collects info about Fuel installation
    Master nodes, clusters, networks, e.t.c.
    Used for collecting info for fuel statistics
    """

    attributes_white_list = (
        # ((path, to, property), 'map_to_name')
        (('common', 'libvirt_type', 'value'), 'libvirt_type'),
        (('common', 'debug', 'value'), 'debug_mode'),
        (('common', 'use_cow_images', 'value'), 'use_cow_images'),

        (('nsx_plugin', 'metadata', 'enabled'), 'nsx'),
        (('nsx_plugin', 'connector_type', 'value'), 'nsx_transport'),
        (('nsx_plugin', 'replication_mode', 'value'), 'nsx_replication'),

        (('vcenter', 'use_vcenter', 'value'), 'vcenter'),
        (('public_network_assignment', 'assign_to_all_nodes', 'value'),
         'assign_public_to_all_nodes'),
        (('syslog', 'syslog_transport', 'value'), 'syslog_transport'),
        (('provision', 'method', 'value'), 'provision_method'),
        (('kernel_params', 'kernel', 'value'), 'kernel_params'),

        (('storage', 'volumes_lvm', 'value'), 'volumes_lvm'),
        (('storage', 'volumes_vmdk', 'value'), 'volumes_vmdk'),
        (('storage', 'iser', 'value'), 'iser'),
        (('storage', 'volumes_ceph', 'value'), 'volumes_ceph'),
        (('storage', 'images_ceph', 'value'), 'images_ceph'),
        (('storage', 'images_vcenter', 'value'), 'images_vcenter'),
        (('storage', 'ephemeral_ceph', 'value'), 'ephemeral_ceph'),
        (('storage', 'objects_ceph', 'value'), 'objects_ceph'),
        (('storage', 'osd_pool_size', 'value'), 'osd_pool_size'),

        (('neutron_mellanox', 'plugin', 'value'), 'mellanox'),
        (('neutron_mellanox', 'vf_num', 'value'), 'mellanox_vf_num'),

        (('additional_components', 'sahara', 'value'), 'sahara'),
        (('additional_components', 'murano', 'value'), 'murano'),
        (('additional_components', 'heat', 'value'), 'heat'),
        (('additional_components', 'ceilometer', 'value'), 'ceilometer'),

        (('vlan_splinters', 'metadata', 'enabled'), 'vlan_splinters'),
        (('vlan_splinters', 'vswitch', 'value'), 'vlan_splinters_ovs')
    )

    def fuel_release_info(self):
        versions = utils.get_fuel_release_versions(settings.FUEL_VERSION_FILE)
        if settings.FUEL_VERSION_KEY not in versions:
            versions[settings.FUEL_VERSION_KEY] = settings.VERSION
        return versions[settings.FUEL_VERSION_KEY]

    def get_clusters_info(self):
        clusters = ClusterCollection.all()
        clusters_info = []
        for cluster in clusters:
            release = cluster.release
            nodes_num = NodeCollection.filter_by(
                None, cluster_id=cluster.id).count()
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
                'attributes': self.get_attributes(cluster.attributes.editable),
                'net_provider': cluster.net_provider,
                'fuel_version': cluster.fuel_version,
                'is_customized': cluster.is_customized
            }
            clusters_info.append(cluster_info)
        return clusters_info

    def get_attributes(self, attributes):
        result = {}
        for path, map_to_name in self.attributes_white_list:
            attr = attributes
            try:
                for p in path:
                    attr = attr[p]
                result[map_to_name] = attr
            except (KeyError, TypeError):
                pass
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

    def get_installation_info(self):
        clusters_info = self.get_clusters_info()
        allocated_nodes_num = sum([c['nodes_num'] for c in clusters_info])
        unallocated_nodes_num = NodeCollection.filter_by(
            None, cluster_id=None).count()

        info = {
            'master_node_uid': self.get_master_node_uid(),
            'fuel_release': self.fuel_release_info(),
            'clusters': clusters_info,
            'clusters_num': len(clusters_info),
            'allocated_nodes_num': allocated_nodes_num,
            'unallocated_nodes_num': unallocated_nodes_num
        }

        return info

    def get_master_node_uid(self):
        return MasterNodeSettings.get_one().master_node_uid
