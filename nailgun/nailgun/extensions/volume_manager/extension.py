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
from nailgun.errors import errors
from nailgun.extensions import BaseExtension
from nailgun.extensions import BasePipeline
from nailgun.logger import logger
from nailgun.objects import Node
from nailgun.objects import Notification
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
            Notification.create({
                'topic': 'error',
                'message': msg,
                'node_id': node.id})

        if node.cluster_id:
            Node.add_pending_change(node, 'disks')


class NodeVolumesPipeline(VolumeObjectMethodsMixin, BasePipeline):

    @classmethod
    def process_provisioning(cls, provisioning_data, cluster, nodes, **kwargs):
        nodes_db = {node.id: node for node in nodes}

        for node in provisioning_data['nodes']:
            volumes = cls.get_node_volumes(nodes_db[int(node['uid'])])
            node['ks_meta']['pm_data']['ks_spaces'] = volumes

        return provisioning_data

    @classmethod
    def process_deployment(cls, deployment_data, cluster, nodes, **kwargs):
        nodes_dict = {int(node['uid']): node for node in deployment_data}

        if StrictVersion(cluster.release.environment_version) \
                >= StrictVersion('8.0'):
            for node in nodes:
                volumes = cls.get_node_volumes(node)
                nodes_dict[node.id]['node_volumes'] = volumes

        return deployment_data


class PgCountPipeline(VolumeObjectMethodsMixin, BasePipeline):

    @classmethod
    def process_deployment(cls, deployment_data, cluster, nodes, **kwargs):
        cls._set_pg_count_storage_parameters(deployment_data, nodes)
        return deployment_data

    @classmethod
    def _set_pg_count_storage_parameters(cls, data, nodes):
        """Generate pg_num

        pg_num is generated as the number of OSDs across the cluster
        multiplied by 100, divided by Ceph replication factor, and
        rounded up to the nearest power of 2.
        """
        osd_num = 0
        osd_nodes = [node for node in nodes
                     if 'ceph-osd' in node.all_roles]

        for node in osd_nodes:
            for disk in cls.get_node_volumes(node):
                for part in disk.get('volumes', []):
                    if part.get('name') == 'ceph' and part.get('size', 0) > 0:
                        osd_num += 1

        for node in data:
            storage_attrs = node['storage']

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


class SetImageCacheMaxSizePipeline(VolumeObjectMethodsMixin, BasePipeline):

    @classmethod
    def process_deployment(cls, deployment_data, cluster, nodes, **kwargs):
        cls._set_image_cache_max_size(deployment_data, cluster, nodes)
        return deployment_data

    @classmethod
    def _set_image_cache_max_size(cls, data, cluster, nodes):
        nodes_db = {node.id: node for node in nodes}

        storage_attrs = cluster.attributes['editable']['storage']
        images_ceph = storage_attrs['images_ceph']['value']

        for node in data:
            if images_ceph:
                image_cache_max_size = '0'
            else:
                volumes = cls.get_node_volumes(nodes_db[int(node['uid'])])
                image_cache_max_size = calc_glance_cache_size(volumes)

            if 'glance' in node:
                node['glance']['image_cache_max_size'] = image_cache_max_size
            else:
                node['glance'] = {'image_cache_max_size': image_cache_max_size}


class VolumeManagerExtension(VolumeObjectMethodsMixin, BaseExtension):

    name = 'volume_manager'
    version = '1.0.0'
    description = "Volume Manager Extension"
    data_pipelines = [
        NodeVolumesPipeline,
        PgCountPipeline,
        SetImageCacheMaxSizePipeline,
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
    def on_node_reset(cls, node):
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
    def on_before_deployment_check(cls, cluster):
        cls._check_disks(cluster)
        cls._check_volumes(cluster)

    @classmethod
    def _is_disk_checking_required(cls, node):
        """Disk checking required in case if node is not provisioned."""
        if node.status in (consts.NODE_STATUSES.ready,
                           consts.NODE_STATUSES.deploying,
                           consts.NODE_STATUSES.provisioned) or \
                (node.status == consts.NODE_STATUSES.error and
                 node.error_type != consts.NODE_ERRORS.provision):
            return False

        return True

    @classmethod
    def _check_disks(cls, cluster):
        try:
            for node in cluster.nodes:
                if cls._is_disk_checking_required(node):
                    VolumeManager(node).check_disk_space_for_deployment()
        except errors.NotEnoughFreeSpace:
            raise errors.NotEnoughFreeSpace(
                u"Node '{}' has insufficient disk space".format(
                    node.human_readable_name))

    @classmethod
    def _check_volumes(cls, cluster):
        try:
            for node in cluster.nodes:
                if cls._is_disk_checking_required(node):
                    VolumeManager(node).check_volume_sizes_for_deployment()
        except errors.NotEnoughFreeSpace as e:
            raise errors.NotEnoughFreeSpace(
                u"Node '{}' has insufficient disk space\n{}}".format(
                    node.human_readable_name, e.message))
