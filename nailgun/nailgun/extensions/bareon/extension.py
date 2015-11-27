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

from nailgun.extensions import BaseExtension
from nailgun.extensions.bareon.adapters import BareonAPIAdapter


class BareonExtension(BaseExtension):
    name = 'bareon'
    version = '1.0.0'
    provides = [
        'get_node_simple_volumes',
    ]
    bareon_adapter = BareonAPIAdapter()

    @classmethod
    def get_node_simple_volumes(cls, node):
        "Simple means: 'in simple nailgun format for fuel-agent'"
        return cls.bareon_adapter.partitioning(node.id)

    @classmethod
    def _put_disks(cls, node):
        disks = []
        for disk in map(lambda d: d.render(), node.volume_manager.disks):
            disk.pop('volumes')
            disk['device'] = disk['name']
            disks.append(disk)

        cls.bareon_adapter.disks(node.id, data=disks)

    @classmethod
    def on_node_update(cls, node):
        if not cls.bareon_adapter.exists(node.id):
            cls.on_node_create(node)
        else:
            cls._put_disks(node)

    @classmethod
    def on_node_collection_delete(cls, node_ids):
        for node_id in node_ids:
            cls.bareon_adapter.delete_node(node_id)

    @classmethod
    def on_node_delete(cls, node):
        cls.bareon_adapter.delete_node(node.id)

    @classmethod
    def on_node_reset(cls, node):
        cls.on_node_delete(node)

    @classmethod
    def on_node_create(cls, node):
        cls.bareon_adapter.create_node({'id': node.id})
        cls._put_disks(node)
