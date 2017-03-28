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

from distutils.version import StrictVersion
import os

import six

from nailgun import consts
from nailgun import errors
from nailgun.extensions import BaseExtension
from nailgun.extensions import BasePipeline
from nailgun.logger import logger
from nailgun import objects
from nailgun.utils.ceph import get_pool_pg_count

from .handlers.disks import NodeDefaultsDisksHandler
from .handlers.disks import NodeDisksHandler
from .handlers.disks import NodeVolumesInformationHandler
from .manager import calc_glance_cache_size
from .manager import VolumeManager


class VolumeObjectMethodsMixin(object):

    @classmethod
    def get_node_volumes(cls, node):
        from .objects.volumes import VolumeObject
        return VolumeObject.get_volumes(node)

    @classmethod
    def set_node_volumes(cls, node, volumes):
        from .objects.volumes import VolumeObject
        return VolumeObject.set_volumes(node, volumes)

    @classmethod
    def set_default_node_volumes(cls, node):
        from .objects.volumes import VolumeObject

        try:
            VolumeObject.set_default_node_volumes(node)
        except Exception as exc:
            logger.exception(exc)
            msg = "Failed to generate volumes for node '{0}': '{1}'".format(
                node.human_readable_name, six.text_type(exc))
            objects.Notification.create({
                'topic': 'error',
                'message': msg,
                'node_id': node.id})

        if node.cluster_id:
            objects.Node.add_pending_change(node, 'disks')


class NodeVolumesPipeline(VolumeObjectMethodsMixin, BasePipeline):

    MIN_SUPPORTED_VERSION = StrictVersion("8.0")

    @classmethod
    def process_provisioning_for_node(cls, node, node_data):
        """Adds node volumes to provision info."""
        ks_meta = node_data.setdefault('ks_meta', {})
        pm_data = ks_meta.setdefault('pm_data', {})
        pm_data['ks_spaces'] = cls.get_node_volumes(node) or []

    @classmethod
    def process_deployment_for_node(cls, node, node_data):
        """Adds node volumes to deployment info."""
        version = StrictVersion(node.cluster.release.environment_version)
        if version >= cls.MIN_SUPPORTED_VERSION:
            node_data['node_volumes'] = cls.get_node_volumes(node) or []


class PgCountPipeline(VolumeObjectMethodsMixin, BasePipeline):

    @classmethod
    def process_deployment_for_cluster(cls, cluster, cluster_data):
        """Added ceph related information to deployment info for cluster."""
        storage_attrs = cluster_data.setdefault('storage', {})

        if 'pg_num' in storage_attrs and 'per_pool_pg_nums' in storage_attrs:
            logger.debug("pg_num %s and per_pool_pg_nums %s are already "
                         "calculated for cluster %s. Getting values from "
                         "the cluster attributes", storage_attrs['pg_num'],
                         storage_attrs['per_pool_pg_nums'], cluster.id)
            return

        all_nodes = {n.uid: n for n in cluster.nodes}
        osd_num = 0
        for n in cluster_data['nodes']:
            if 'ceph-osd' in (n.get('roles') or [n.get('role')]):
                volumes = cls.get_node_volumes(all_nodes[n['uid']]) or []
                for volume in volumes:
                    for part in volume.get('volumes', []):
                        if (part.get('name') == 'ceph' and
                                part.get('size', 0) > 0):
                            osd_num += 1

        pg_counts = get_pool_pg_count(
            osd_num=osd_num,
            pool_sz=int(storage_attrs['osd_pool_size']),
            ceph_version='firefly',
            volumes_ceph=storage_attrs['volumes_ceph'],
            objects_ceph=storage_attrs['objects_ceph'],
            ephemeral_ceph=storage_attrs['ephemeral_ceph'],
            images_ceph=storage_attrs['images_ceph'],
            emulate_pre_7_0=False)

        # Log {pool_name: pg_count} mapping
        pg_str = ", ".join(map("{0[0]}={0[1]}".format, pg_counts.items()))
        logger.debug("Ceph: PG values {%s}", pg_str)
        storage_attrs['pg_num'] = pg_counts['default_pg_num']
        storage_attrs['per_pool_pg_nums'] = pg_counts

        cls._save_storage_attrs(cluster, storage_attrs['pg_num'],
                                storage_attrs['per_pool_pg_nums'])

    @classmethod
    def _save_storage_attrs(cls, cluster, pg_num, per_pool_pg_nums):
        attrs = objects.Cluster.get_attributes(cluster)
        logger.debug("Saving pg_num and per_pool_pg_nums values to "
                     "cluster attributes")
        attrs['editable']['storage']['pg_num'] = \
            {'value': pg_num, 'type': 'hidden'}
        attrs['editable']['storage']['per_pool_pg_nums'] = \
            {'value': per_pool_pg_nums, 'type': 'hidden'}
        objects.Cluster.update_attributes(cluster, attrs)


class SetImageCacheMaxSizePipeline(VolumeObjectMethodsMixin, BasePipeline):

    @classmethod
    def process_deployment_for_node(cls, node, node_data):
        """Added glance related information to deployment info for node."""
        volumes = cls.get_node_volumes(node)
        image_cache_max_size = calc_glance_cache_size(volumes)
        glance = node_data.setdefault('glance', {})
        glance['image_cache_max_size'] = image_cache_max_size


class VolumeManagerExtension(VolumeObjectMethodsMixin, BaseExtension):

    name = 'volume_manager'
    version = '1.0.0'
    description = "Volume Manager Extension"
    data_pipelines = [
        NodeVolumesPipeline,
        PgCountPipeline,
        SetImageCacheMaxSizePipeline,
    ]
    provides = [
        'get_node_volumes',
        'set_node_volumes',
        'set_default_node_volumes'
    ]

    @classmethod
    def alembic_migrations_path(cls):
        return os.path.join(os.path.dirname(__file__),
                            'alembic_migrations', 'migrations')

    urls = [
        {'uri': r'/nodes/(?P<node_id>\d+)/disks/?$',
         'handler': NodeDisksHandler},
        {'uri': r'/nodes/(?P<node_id>\d+)/disks/defaults/?$',
         'handler': NodeDefaultsDisksHandler},
        {'uri': r'/nodes/(?P<node_id>\d+)/volumes/?$',
         'handler': NodeVolumesInformationHandler}]

    @classmethod
    def on_node_create(cls, node):
        cls.set_default_node_volumes(node)

    @classmethod
    def on_node_update(cls, node):
        cls.set_default_node_volumes(node)

    @classmethod
    def on_node_delete(cls, node):
        from .objects.volumes import VolumeObject
        VolumeObject.delete_by_node_ids([node.id])

    @classmethod
    def on_node_collection_delete(cls, node_ids):
        from .objects.volumes import VolumeObject
        VolumeObject.delete_by_node_ids(node_ids)

    @classmethod
    def on_before_deployment_check(cls, cluster, nodes):
        cls._check_disks(nodes)
        cls._check_volumes(nodes)

    @classmethod
    def _is_disk_checking_required(cls, node):
        """True if node disk requires checking

        :param node: Node (model) instance
        :returns: bool
        """
        if (node.status in (consts.NODE_STATUSES.ready,
                            consts.NODE_STATUSES.deploying,
                            consts.NODE_STATUSES.provisioned) or
                (node.status == consts.NODE_STATUSES.error and
                 node.error_type != consts.NODE_ERRORS.provision)):
            return False

        return True

    @classmethod
    def _check_disks(cls, nodes):
        cls._check_spaces(
            nodes, lambda vm: vm.check_disk_space_for_deployment()
        )

    @classmethod
    def _check_volumes(cls, nodes):
        cls._check_spaces(
            nodes, lambda vm: vm.check_volume_sizes_for_deployment()
        )

    @classmethod
    def _check_spaces(cls, nodes, checker):
        messages = []
        for node in nodes:
            if cls._is_disk_checking_required(node):
                try:
                    checker(VolumeManager(node))
                except errors.NotEnoughFreeSpace:
                    messages.append(
                        u"Node '{}' has insufficient disk space"
                        .format(node.human_readable_name)
                    )
        if messages:
            raise errors.NotEnoughFreeSpace(u'\n'.join(messages))
