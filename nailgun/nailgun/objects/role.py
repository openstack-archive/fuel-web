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

from nailgun.api.v1.validators.json_schema.role import SCHEMA
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects import Release
from nailgun.objects.serializers.role import RoleSerializer


class Role(NailgunObject):

    model = models.Role
    schema = SCHEMA
    serializer = RoleSerializer

    @classmethod
    def update_meta(cls, role, data):
        # at least some volumes should be created, and it is mandatory
        # to validate it before creation
        volumes = data['volumes']

        if not volumes:
            raise errors.NotEnoughData(
                "At least one volume should be provided")

        meta = data['meta']

        release = role.release
        release.roles_metadata[role.name] = meta
        release.volumes_metadata['volumes_roles_mapping'][role.name] = volumes

    @classmethod
    def create(cls, data):
        release = Release.get_by_uid(data['release_id'])
        role = cls.model(name=data['name'], release=release)

        cls.update_meta(role, data)

        db().add(role)
        db().flush()

        return role

    @classmethod
    def update(cls, role, data):
        role.name = data['name']
        role.release_id = data['relese_id']

        db().flush()

        cls.update_meta(role, data)

        return role


class RoleCollection(NailgunCollection):

    single = Role
