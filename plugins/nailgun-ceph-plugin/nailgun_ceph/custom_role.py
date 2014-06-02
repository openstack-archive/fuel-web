# -*- coding: utf-8 -*-

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

import math
import os

from nailgun import objects

from nailgun.plugins.classes import StoragePlugin

from nailgun.volumes.manager import gb_to_mb


class CephRolePlugin(StoragePlugin):

    __plugin_name__ = "ceph_plugin"

    config_file = os.path.join(
        os.path.dirname(__file__),
        "config.yaml"
    )

    generators = {
        # 2GB required for journal, leave 1GB for data
        'calc_min_ceph_size': lambda: gb_to_mb(3),
        'calc_min_ceph_journal_size': lambda: 0
    }

    def process_cluster_attributes(self, cluster_id, attributes):
        images_ceph = attributes["editable"]["storage"].get("images_ceph")
        if images_ceph and images_ceph["value"]:
            with self.storage as storage:
                storage.add_record(
                    "cluster_attribute",
                    {"images_ceph": True, "cluster_id": cluster_id}
                )
        return attributes

    def process_volumes_metadata(self, volumes_metadata, node=None):
        res = super(CephRolePlugin, self).process_volumes_metadata(
            volumes_metadata
        )
        # TODO(dshulyak)
        # This logic should go to openstack.yaml (or other template)
        # when it will be extended with flexible template engine
        #
        # hack to remove Glance partition
        if node:
            images_ceph = self.storage.search_records(
                record_type="cluster_attribute",
                cluster_id=node.cluster_id,
                images_ceph=True
            )
            if images_ceph:
                res["volumes_roles_mapping"]['controller'] = \
                    filter(
                        lambda space: space['id'] != 'image',
                        res["volumes_roles_mapping"]['controller']
                    )
        return res

    def process_node_attrs(self, node, node_attrs):
        if node:
            images_ceph = self.storage.search_records(
                record_type="cluster_attribute",
                cluster_id=node.cluster_id,
                images_ceph=True
            )
            if images_ceph:
                node_attrs["glance"]["image_cache_max_size"] = "0"
        return node_attrs

    def process_cluster_attrs(self, cluster, cluster_attrs):
        """Generate pg_num as the number of OSDs across the cluster
        multiplied by 100, divided by Ceph replication factor, and
        rounded up to the nearest power of 2.
        """
        osd_num = 0

        q = objects.NodeCollection.filter_by_role_or_pending_role(
            objects.NodeCollection.filter_by(
                None,
                cluster_id=cluster.id
            ),
            'ceph-osd'
        )
        ceph_nodes = objects.NodeCollection.eager(q, ["attributes"])

        for node in ceph_nodes:
            for disk in objects.Node.get_volumes(node):
                for part in disk.get('volumes', []):
                    if part.get('name') == 'ceph' and part.get('size', 0) > 0:
                        osd_num += 1
        if osd_num > 0:
            repl = int(cluster_attrs['storage']['osd_pool_size'])
            pg_num = 2 ** int(math.ceil(math.log(osd_num * 100.0 / repl, 2)))
        else:
            pg_num = 128
        cluster_attrs['storage']['pg_num'] = pg_num
        return cluster_attrs
