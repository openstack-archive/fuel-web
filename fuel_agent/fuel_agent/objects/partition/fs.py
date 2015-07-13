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

from fuel_agent.objects import base


class FileSystem(base.BasePartition):

    def __init__(self, device, mount=None, fs_type=None,
                 fs_options=None, fs_label=None, **kwargs):
        super(FileSystem, self).__init__(**kwargs)
        self.device = device
        self.mount = mount
        self.type = fs_type or 'xfs'
        self.options = fs_options or ''
        self.label = fs_label or ''

    def to_dict(self):
        data = super(FileSystem, self).to_dict()
        data.update({
            'device': self.device,
            'mount': self.mount,
            'fs_type': self.type,
            'fs_options': self.options,
            'fs_label': self.label,
        })
        return data
