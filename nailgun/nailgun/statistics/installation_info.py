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

import six

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

    def sanitise_data(self, data):
        to_sanitation = ('password', 'login', 'username', 'user', 'passwd',
                         'network_data', 'ip_addr', 'cidr', 'vlan_start', 'ip',
                         'net', 'network', 'address', 'ip_address', 'vlan',
                         'vlan_range', 'base_mac', 'mac', 'internal_cidr',
                         'internal_gateway', 'gateway', 'netmask',
                         'floating_ranges')

        if isinstance(data, (list, tuple)):
            result = []
            for v in data:
                processed = self.sanitise_data(v)
                result.append(processed)
            return result
        elif isinstance(data, dict):
            result = {}
            for k, v in six.iteritems(data):
                if k not in to_sanitation:
                    result[k] = self.sanitise_data(v)
            return result
        else:
            return data

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
                'status': cluster.status,
                'attributes': self.sanitise_data(cluster.attributes.editable)
            }
            clusters_info.append(cluster_info)
        return clusters_info

    def get_nodes_info(self, nodes):
        nodes_info = []
        for node in nodes:
            node_info = {
                'id': node.id,
                'roles': node.roles,
                'os': node.os_platform,
                'status': node.status
            }
            nodes_info.append(node_info)
        return nodes_info

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
