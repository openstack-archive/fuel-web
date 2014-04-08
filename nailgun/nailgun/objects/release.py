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

"""
Release object and collection
"""

from sqlalchemy import not_

from nailgun import consts

from nailgun.api.serializers.release import ReleaseSerializer

from nailgun.db import db

from nailgun.db.sqlalchemy.models import Release as DBRelease
from nailgun.db.sqlalchemy.models import \
    ReleaseOrchestratorData as DBReleaseOrchData
from nailgun.db.sqlalchemy.models import Role as DBRole

from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject

from nailgun.settings import settings


class ReleaseOrchestratorData(NailgunObject):
    """ReleaseOrchestratorData object
    """

    #: SQLAlchemy model
    model = DBReleaseOrchData

    #: JSON schema
    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "ReleaseOrchestratorData",
        "description": "Serialized ReleaseOrchestratorData object",
        "type": "object",
        "required": [
            "release_id"
        ],
        "properties": {
            "id": {"type": "number"},
            "release_id": {"type": "number"},
            "repo": {"type": "string"},
            "puppet_base": {"type": "string"}
        }
    }


class Release(NailgunObject):
    """Release object
    """

    #: SQLAlchemy model for Release
    model = DBRelease

    #: Serializer for Release
    serializer = ReleaseSerializer

    #: Release JSON schema
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
        """Create Release instance with specified parameters in DB.
        Corresponding roles are created in DB using names specified
        in "roles" field. See :func:`update_roles`

        :param data: dictionary of key-value pairs as object fields
        :returns: Release instance
        """
        roles = data.pop("roles", None)
        orch_data = data.pop("orch_data", None)
        new_obj = super(Release, cls).create(data)
        if roles:
            cls.update_roles(new_obj, roles)
        if orch_data:
            ReleaseOrchestratorData.create(orch_data)
        return new_obj

    @classmethod
    def update(cls, instance, data):
        """Update existing Release instance with specified parameters.
        Corresponding roles are updated in DB using names specified
        in "roles" field. See :func:`update_roles`

        :param instance: Release instance
        :param data: dictionary of key-value pairs as object fields
        :returns: Release instance
        """
        roles = data.pop("roles", None)
        super(Release, cls).update(instance, data)
        if roles is not None:
            cls.update_roles(instance, roles)
        return instance

    @classmethod
    def update_roles(cls, instance, roles):
        """Update existing Release instance with specified roles.
        Previous ones are deleted.

        IMPORTANT NOTE: attempting to remove roles that are already
        assigned to nodes will lead to an Exception.

        :param instance: Release instance
        :param roles: list of new roles names
        :returns: None
        """
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

    @classmethod
    def repo_metadata(cls, instance):
        if not instance.orchestrator_data:
            return {}
        return {
            "nailgun": "http://{0}:{1}/{2}".format(
                settings.MASTER_IP,
                settings.REPO_PORT,
                instance.orchestrator_data.repo)
        }

    @classmethod
    def puppet_source(cls, instance, payload):
        if not instance.orchestrator_data:
            return ""
        return "rsync://{0}/{1}/{2}/{3}".format(
            settings.MASTER_IP,
            instance.orchestrator_data.puppet_base,
            instance.version,
            payload
        )

    @classmethod
    def puppet_modules_source(cls, instance):
        cls.puppet_source(instance, 'modules')

    @classmethod
    def puppet_manifests_source(cls, instance):
        cls.puppet_source(instance, 'manifests')


class ReleaseCollection(NailgunCollection):
    """Release collection
    """

    #: Single Release object class
    single = Release
