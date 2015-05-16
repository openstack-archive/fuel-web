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
from distutils.version import StrictVersion
from sqlalchemy import not_
import yaml

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers import release as release_serializer
from nailgun.orchestrator import graph_configuration
from nailgun.settings import settings
from nailgun.utils import extract_env_version


class Release(NailgunObject):
    """Release object
    """

    #: SQLAlchemy model for Release
    model = models.Release

    #: Serializer for Release
    serializer = release_serializer.ReleaseSerializer

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
            "clusters": {"type": "array"},
            "is_deployable": {"type": "boolean"},
            "vmware_attributes_metadata": {"type": "object"}
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
        new_obj = super(Release, cls).create(data)
        if roles:
            cls.update_roles(new_obj, roles)
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
    def is_deployable(cls, instance):
        """Returns whether a given release deployable or not.

        :param instance: a Release instance
        :returns: True if a given release is deployable; otherwise - False
        """
        # in experimental mode we deploy all releases
        if 'experimental' in settings.VERSION['feature_groups']:
            return True
        return instance.is_deployable

    @classmethod
    def is_granular_enabled(cls, instance):
        """Check if granular deployment is available for release

        :param instance: a Release instance
        :returns: boolean
        """
        return (StrictVersion(instance.fuel_version) >=
                StrictVersion(consts.FUEL_GRANULAR_DEPLOY))

    @classmethod
    def get_deployment_tasks(cls, instance):
        """Get deployment graph based on release version."""
        env_version = extract_env_version(instance.version)
        if instance.deployment_tasks:
            return instance.deployment_tasks
        elif env_version.startswith('5.0'):
            return yaml.load(graph_configuration.DEPLOYMENT_50)
        elif env_version.startswith('5.1') or env_version.startswith('6.0'):
            return yaml.load(graph_configuration.DEPLOYMENT_51_60)


class ReleaseCollection(NailgunCollection):
    """Release collection
    """

    #: Single Release object class
    single = Release
