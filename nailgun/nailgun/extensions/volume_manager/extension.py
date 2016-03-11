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

import os

import six

from nailgun.extensions import BaseExtension
from nailgun.extensions import BasePipeline
from nailgun.logger import logger
from nailgun.objects import Node
from nailgun.objects import Notification

from .handlers.disks import NodeDefaultsDisksHandler
from .handlers.disks import NodeDisksHandler
from .handlers.disks import NodeVolumesInformationHandler


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
    def process_provisioning(cls, data, cluster, nodes, **kwargs):
        nodes_db = {node.id: node for node in nodes}

        for node in data['nodes']:
            volumes = cls.get_node_volumes(nodes_db[int(node['uid'])])
            node['ks_meta']['pm_data']['ks_spaces'] = volumes

        return data


class VolumeManagerExtension(VolumeObjectMethodsMixin, BaseExtension):

    name = 'volume_manager'
    version = '1.0.0'
    provides = [
        'get_node_volumes',
        'set_node_volumes',
        'set_default_node_volumes']

    description = "Volume Manager Extension"
    data_pipelines = [
        NodeVolumesPipeline,
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
