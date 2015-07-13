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


class PhysicalVolume(base.BasePartition):

    def __init__(self, name, metadatasize=16, metadatacopies=2, **kwargs):
        super(PhysicalVolume, self).__init__(**kwargs)
        self.name = name
        self.metadatasize = metadatasize
        self.metadatacopies = metadatacopies

    def to_dict(self):
        data = super(PhysicalVolume, self).to_dict()
        data.update({
            'name': self.name,
            'metadatasize': self.metadatasize,
            'metadatacopies': self.metadatacopies,
        })
        return data
