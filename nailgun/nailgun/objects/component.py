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

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.plugin import PluginCollection
from nailgun.objects import Release
from nailgun.objects.serializers import component


class Component(NailgunObject):

    model = models.Component
    serializer = component.ComponentSerializer

    @classmethod
    def get_by_name(cls, name):
        return db().query(cls.model).filter_by(name=name).first()


class ComponentCollection(NailgunCollection):

    single = Component

    @classmethod
    def get_all_by_release(cls, release_id):
        core_components = Release.get_by_uid(release_id).components
        plugin_components = []
        for db_plugin in PluginCollection.get_all_by_release(release_id):
            for plugin_component in db_plugin.components:
                if plugin_component not in plugin_components:
                    plugin_components.append(plugin_component)

        return core_components + plugin_components
