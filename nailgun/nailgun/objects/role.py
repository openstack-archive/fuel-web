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

from copy import deepcopy

from nailgun.api.v1.validators.json_schema.role import SCHEMA
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects import Release
from nailgun.objects.serializers.role import RoleSerializer


class Role(NailgunObject):

    model = models.Role
    schema = SCHEMA
    serializer = RoleSerializer

    @classmethod
    def _update_release(cls, role, data):
        volumes = data.get('volumes', {})
        meta = data.get('meta', {})

        cls._update_volumes(role, volumes)
        cls._update_meta(role, meta)

    @classmethod
    def _update_volumes(cls, role, volumes):
        release = role.release
        volumes_meta = deepcopy(release.volumes_metadata)
        volumes_meta['volumes_roles_mapping'][role.name] = volumes
        release.volumes_metadata = volumes_meta

    @classmethod
    def _update_meta(cls, role, meta):
        release = role.release
        roles_meta = deepcopy(release.roles_metadata)
        roles_meta[role.name] = meta
        release.roles_metadata = roles_meta

    @classmethod
    def create(cls, data):
        release = Release.get_by_uid(data['release_id'])
        role = cls.model(name=data['name'], release=release)

        cls._update_release(role, data)

        db().add(role)
        db().flush()

        return role

    @classmethod
    def update(cls, role, data):
        role.name = data['name']
        role.release_id = data['release_id']

        cls._update_release(role, data)
        db().flush()

        return role

    @classmethod
    def delete(cls, role):
        cls._update_release(role, {})
        return super(Role, cls).delete(role)


class RoleCollection(NailgunCollection):

    single = Role
