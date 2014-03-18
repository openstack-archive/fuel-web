# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from sqlalchemy import not_

from nailgun import consts

from nailgun.api.serializers.release import ReleaseSerializer

from nailgun.db import db

from nailgun.db.sqlalchemy.models import Release as DBRelease
from nailgun.db.sqlalchemy.models import Role as DBRole

from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject


class Release(NailgunObject):

    model = DBRelease
    serializer = ReleaseSerializer

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "Release",
        "description": "Serialized Release object",
        "type": "object",
        "required": [
            "name",
            "operating_system"
        ],
        "properties": {
            "id": {"type": "number"},
            "name": {"type": "string"},
            "version": {"type": "string"},
            "description": {"type": "string"},
            "operating_system": {"type": "string"},
            "state": {
                "type": "string",
                "enum": list(consts.RELEASE_STATES)
            },
            "networks_metadata": {"type": "array"},
            "attributes_metadata": {"type": "object"},
            "volumes_metadata": {"type": "object"},
            "modes_metadata": {"type": "object"},
            "roles_metadata": {"type": "object"},
            "roles": {"type": "array"},
            "clusters": {"type": "array"}
        }
    }

    @classmethod
    def create(cls, data):
        roles = data.pop("roles", None)
        new_obj = super(Release, cls).create(data)
        if roles:
            cls.update_roles(new_obj, roles)
        return new_obj

    @classmethod
    def update(cls, instance, data):
        roles = data.pop("roles", None)
        super(Release, cls).update(instance, data)
        if roles is not None:
            cls.update_roles(instance, roles)
        return instance

    @classmethod
    def update_roles(cls, instance, roles):
        db().query(DBRole).filter(
            not_(DBRole.name.in_(roles))
        ).filter(
            DBRole.release_id == instance.id
        ).delete(synchronize_session='fetch')
        db().refresh(instance)

        added_roles = instance.roles
        for role in roles:
            if role not in added_roles:
                new_role = DBRole(
                    name=role,
                    release=instance
                )
                db().add(new_role)
                added_roles.append(role)
        db().flush()


class ReleaseCollection(NailgunCollection):

    single = Release
