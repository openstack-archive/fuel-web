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

from sqlalchemy.orm import joinedload

from nailgun.db import db
from nailgun.db.sqlalchemy import models

from .base import NailgunCollection
from .base import NailgunObject
from .release import Release
from .serializers import component


class Component(NailgunObject):

    model = models.Component
    serializer = component.ComponentSerializer

    @classmethod
    def get_by_name_and_type(cls, component_name, component_type):
        return db().query(cls.model).filter_by(
            name=component_name, type=component_type).first()


class ComponentCollection(NailgunCollection):

    single = Component

    @classmethod
    def get_all_by_release(cls, release_id):
        """Get all components for specific release.

        :param release_id: release ID
        :type release_id: int

        :returns: list -- list of components
        """
        components = []
        release = Release.get_by_uid(release_id)
        release_os = release.operating_system.lower()
        release_version = release.version

        db_components = db().query(cls.single.model).options(
            joinedload(cls.single.model.releases),
            joinedload(cls.single.model.plugin)).all()

        for db_component in db_components:
            if db_component.releases:
                for db_release in db_component.releases:
                    if db_release.id == release.id:
                        components.append(db_component)
            elif db_component.plugin:
                for plugin_release in db_component.plugin.releases:
                    if (release_os == plugin_release.get('os') and
                            release_version == plugin_release.get('version')):
                        components.append(db_component)

        return components
