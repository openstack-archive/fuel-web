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
from nailgun.objects import NodeCollection
from nailgun.settings import settings
from nailgun import utils


class InstallationInfo(object):
    """Collects info about Fuel installation
    Master nodes, clusters, networks, e.t.c.
    Used for collecting info for fuel statistics
    """

    FUEL_VERSION_FILE = '/etc/fuel/version.yaml'
    FUEL_VERSION_KEY = 'VERSION'

    def fuel_release_info(self):
        versions = utils.get_fuel_release_versions(self.FUEL_VERSION_FILE)
        if self.FUEL_VERSION_KEY not in versions:
            versions[self.FUEL_VERSION_KEY] = settings.VERSION
        return versions[self.FUEL_VERSION_KEY]

    def get_clusters_info(self):
        clusters = ClusterCollection.all()
        clusters_info = []
        for cluster in clusters:
            nodes = cluster.nodes
            release = cluster.release
            cluster_info = {
                'id': cluster.id,
                'nodes_num': len(nodes),
                'release': {
                    'os': release.operating_system,
                    'name': release.name,
                    'version': release.version
                },
                'mode': cluster.mode,
                'nodes': self.get_nodes_info(cluster.nodes),
                'status': cluster.status
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
        #TODO(akislitsky): aid should be fetched from MasterNode settigns
        return 'to_be_implemented'
