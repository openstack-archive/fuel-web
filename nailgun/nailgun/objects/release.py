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

from nailgun.objects.serializers.release import ReleaseSerializer

from nailgun.db import db

from nailgun.db.sqlalchemy import models

from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject

from nailgun.settings import settings


class ReleaseOrchestratorData(NailgunObject):
    """ReleaseOrchestratorData object
    """

    #: SQLAlchemy model
    model = models.ReleaseOrchestratorData

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
            "repo_metadata": {"type": "object"},
            "puppet_manifests_source": {"type": "string"},
            "puppet_modules_source": {"type": "string"}
        }
    }


class Release(NailgunObject):
    """Release object
    """

    #: SQLAlchemy model for Release
    model = models.Release

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
            "can_update_from_versions": {"type": "array"},
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
            "wizard_metadata": {"type": "object"},
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
        orch_data = data.pop("orchestrator_data", None)
        new_obj = super(Release, cls).create(data)
        if roles:
            cls.update_roles(new_obj, roles)
        if orch_data:
            orch_data["release_id"] = new_obj.id
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
        orch_data = data.pop("orchestrator_data", None)
        super(Release, cls).update(instance, data)
        if roles is not None:
            cls.update_roles(instance, roles)
        if orch_data:
            cls.update_orchestrator_data(instance, orch_data)
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
        db().query(models.Role).filter(
            not_(models.Role.name.in_(roles))
        ).filter(
            models.Role.release_id == instance.id
        ).delete(synchronize_session='fetch')
        db().refresh(instance)

        added_roles = instance.roles
        for role in roles:
            if role not in added_roles:
                new_role = models.Role(
                    name=role,
                    release=instance
                )
                db().add(new_role)
                added_roles.append(role)
        db().flush()

    @classmethod
    def update_orchestrator_data(cls, instance, orchestrator_data):
        for k in ["id", "release_id"]:
            orchestrator_data.pop(k, None)
        if orchestrator_data:
            if instance.orchestrator_data:
                ReleaseOrchestratorData.update(
                    instance.orchestrator_data, orchestrator_data)
            else:
                orchestrator_data["release_id"] = instance.id
                ReleaseOrchestratorData.create(orchestrator_data)

    @classmethod
    def get_orchestrator_data_dict(cls, instance):
        os = instance.operating_system.lower()
        default_orchestrator_data = {
            "repo_metadata": {
                "nailgun":
                settings.DEFAULT_REPO[os].format(
                    master_ip=settings.MASTER_IP),
            },
            "puppet_modules_source":
            settings.DEFAULT_PUPPET['modules'].format(
                master_ip=settings.MASTER_IP),
            "puppet_manifests_source":
            settings.DEFAULT_PUPPET['manifests'].format(
                master_ip=settings.MASTER_IP),
        }

        return {
            "repo_metadata":
            instance.orchestrator_data.repo_metadata,
            "puppet_modules_source":
            instance.orchestrator_data.puppet_modules_source,
            "puppet_manifests_source":
            instance.orchestrator_data.puppet_manifests_source
        } if instance.orchestrator_data else default_orchestrator_data


class ReleaseCollection(NailgunCollection):
    """Release collection
    """

    #: Single Release object class
    single = Release
