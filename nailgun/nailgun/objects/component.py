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
    def get_by_name_and_type(cls, component_name, component_type):
        """Get specific component record"""
        return db().query(cls.model).filter_by(
            name=component_name, type=component_type).first()


class ComponentCollection(NailgunCollection):

    single = Component

    @classmethod
    def get_all_by_release(cls, release_id):
        """Get all components for specific release.

        :param release_id: release ID
        :type release_id: int

        :returns: list -- collection of components
        """
        core_components = Release.get_by_uid(release_id).components
        plugins_components = []
        plugins_components_ids = set()
        for db_plugin in PluginCollection.get_all_by_release(release_id):
            for plugin_component in db_plugin.components:
                component_id = plugin_component.id
                if component_id not in plugins_components_ids:
                    plugins_components_ids.add(component_id)
                    plugins_components.append(plugin_component)

        return core_components + plugins_components
