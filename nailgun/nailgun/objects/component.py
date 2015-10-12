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

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers import component


class Component(NailgunObject):

    model = models.Component
    serializer = component.ComponentSerializer

    @classmethod
    def get_by_name(cls, name):
        return db().query(cls.model).filter_by(name=name).first()

    @classmethod
    def create(cls, data):
        data['hypervisor'] = data.pop('compatible_hypervisors', [])
        data['storage'] = data.pop('compatible_storages', [])
        data['networking'] = data.pop('compatible_networking', [])
        data['additional_services'] = data.pop(
            'compatible_additional_services', [])
        return super(Component, cls).create(data)


class ComponentCollection(NailgunCollection):

    single = Component

    @classmethod
    def create(cls, data, plugin_id=None):
        result_collection = []
        for component_data in data:
            component_data['plugin_id'] = plugin_id
            result_collection.append(cls.single.create(component_data))
        return result_collection
