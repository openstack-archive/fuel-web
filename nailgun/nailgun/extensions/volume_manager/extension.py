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


from .handlers.disks import NodeDefaultsDisksHandler
from .handlers.disks import NodeDisksHandler
from .handlers.disks import NodeVolumesInformationHandler

from nailgun.extensions import BaseExtension


class VolumeManagerExtension(BaseExtension):

    urls = [
        {'uri': r'/nodes/(?P<node_id>\d+)/disks/?$',
         'handler': NodeDisksHandler},
        {'uri': r'/nodes/(?P<node_id>\d+)/disks/defaults/?$',
         'handler': NodeDefaultsDisksHandler},
        {'uri': r'/nodes/(?P<node_id>\d+)/volumes/?$',
         'handler': NodeVolumesInformationHandler}]
