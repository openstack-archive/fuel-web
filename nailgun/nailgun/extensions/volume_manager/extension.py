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

from nailgun.extensions import BaseExtension

from .handlers.disks import NodeDefaultsDisksHandler
from .handlers.disks import NodeDisksHandler
from .handlers.disks import NodeVolumesInformationHandler


class VolumeManagerExtension(BaseExtension):

    name = 'volume_manager'
    version = '1.0.0'

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
    def get_volumes(cls, node):
        from .objects.volumes import VolumeObject
        return VolumeObject.get_volumes(node)

    @classmethod
    def set_volumes(cls, node, volumes):
        from .objects.volumes import VolumeObject
        return VolumeObject.set_volumes(node, volumes)
