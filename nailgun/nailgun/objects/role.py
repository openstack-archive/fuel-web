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

from nailgun.objects import base
from nailgun.objects import Release
from nailgun.db.sqlalchemy import models
from nailgun.db import db
from nailgun.errors import errors
from nailgun.api.v1.validators.json_schema.role import SCHEMA


class Role(base.NailgunObject):

    model = models.Role

    schema = SCHEMA

    @classmethod
    def get(cls, release_id, role_name):
        role = db.query(model).filter_by(
            release_id=release_id, name=role_name).first()
        if role is None:
            raise errors.ObjectNotFound(
                "Role for release {release_id} with name {role_name} not found".format(release_id=release_id, role_name=role_name))

    @classmethod
    def update_meta(cls, role, data):
        # at least some volumes should be created, and it is mandatory
        # to validate it before creation
        volumes = data.pop('volumes', None)
        if not volumes:
            raise errors.NotEnoughData(
                "At least one volume should be provided")

        release.roles_metadata[role.name] = data
        release.volumes_metadata['volumes_roles_mapping'][role.name] = volumes

    @classmethod
    def create(cls, release_id, data):
        release = Release.get_by_uid(release_id)

        role = model(name=data['id'], release=release)
        db().add(role)

        cls.update_meta(role, data)

        db().flush()
        return role

    @classmethod
    def update(cls, role, data):

        role.name = data.id

        cls.update_meta(role, data)
        db().flush()

        return role

    @classmethod
    def to_json(cls, role):
        release = role.release
        meta = release.roles_metadata[role.name]
        volumes = release.volumes_metadata['volumes_roles_mapping'][role.name]

        return {
            'id': role.name,
            'name': meta['name'],
            'description': meta['description'],
            'volumes': volumes}

    @classmethod
    def template(cls):
        return self.schema['properties']
