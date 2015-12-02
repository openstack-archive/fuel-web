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
import yaml

from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers import release as release_serializer
from nailgun.orchestrator import graph_configuration
from nailgun.plugins.manager import PluginManager
from nailgun.settings import settings


class Release(NailgunObject):
    """Release object"""

    #: SQLAlchemy model for Release
    model = models.Release

    #: Serializer for Release
    serializer = release_serializer.ReleaseSerializer

    @classmethod
    def create(cls, data):
        """Create Release instance with specified parameters in DB.

        :param data: dictionary of key-value pairs as object fields
        :returns: Release instance
        """
        # in order to be compatible with old API, let's drop input
        # roles array. since fuel 7.0 we don't use it anymore, and
        # we don't require it even for old releases.
        data.pop("roles", None)
        return super(Release, cls).create(data)

    @classmethod
    def update(cls, instance, data):
        """Update existing Release instance with specified parameters.

        :param instance: Release instance
        :param data: dictionary of key-value pairs as object fields
        :returns: Release instance
        """
        # in order to be compatible with old API, let's drop input
        # roles array. since fuel 7.0 we don't use it anymore, and
        # we don't require it even for old releases.
        data.pop("roles", None)
        return super(Release, cls).update(instance, data)

    @classmethod
    def update_role(cls, instance, role):
        """Update existing Release instance with specified role.

        Previous ones are deleted.

        :param instance: a Release instance
        :param role: a role dict
        :returns: None
        """
        instance.roles_metadata[role['name']] = role['meta']
        instance.volumes_metadata['volumes_roles_mapping'][role['name']] = \
            role.get('volumes_roles_mapping', [])
        # Data was changed in second level, so mark attribute as changed
        instance.volumes_metadata.changed()

    @classmethod
    def remove_role(cls, instance, role_name):
        result = instance.roles_metadata.pop(role_name, None)
        # Method pop doesn't implemented in MutableDict,
        # so mark attribute manually as changed
        instance.roles_metadata.changed()
        instance.volumes_metadata['volumes_roles_mapping'].pop(role_name, None)
        # Data was changed in second level, so mark attribute as changed
        instance.volumes_metadata.changed()
        return bool(result)

    @classmethod
    def is_deployable(cls, instance):
        """Returns whether a given release deployable or not.

        :param instance: a Release instance
        :returns: True if a given release is deployable; otherwise - False
        """
        if instance.state == consts.RELEASE_STATES.unavailable:
            return False

        # in experimental mode we deploy all releases
        if 'experimental' in settings.VERSION['feature_groups']:
            return True

        return instance.state == consts.RELEASE_STATES.available

    @classmethod
    def is_granular_enabled(cls, instance):
        """Check if granular deployment is available for release

        :param instance: a Release instance
        :returns: boolean
        """
        return (StrictVersion(instance.environment_version) >=
                StrictVersion(consts.FUEL_GRANULAR_DEPLOY))

    @classmethod
    def is_external_mongo_enabled(cls, instance):
        """Check if external mongo is available for release

        :param instance: a Release instance
        :returns: boolean
        """
        return (StrictVersion(instance.environment_version) >=
                StrictVersion(consts.FUEL_EXTERNAL_MONGO))

    @classmethod
    def is_multiple_floating_ranges_enabled(cls, instance):
        """Check if usage of multiple floating ranges is available for release


        :param instance: a Release instance
        :returns: boolean
        """
        return (StrictVersion(instance.environment_version) >=
                StrictVersion(consts.FUEL_MULTIPLE_FLOATING_IP_RANGES))

    @classmethod
    def get_deployment_tasks(cls, instance):
        """Get deployment graph based on release version."""
        env_version = instance.environment_version
        if instance.deployment_tasks:
            return instance.deployment_tasks
        elif env_version.startswith('5.0'):
            return yaml.load(graph_configuration.DEPLOYMENT_50)
        elif env_version.startswith('5.1') or env_version.startswith('6.0'):
            return yaml.load(graph_configuration.DEPLOYMENT_51_60)

        return []

    @classmethod
    def get_min_controller_count(cls, instance):
        return instance.roles_metadata['controller']['limits']['min']

    @classmethod
    def get_all_components(cls, instance):
        """Get all components related to release

        :param instance: Release instance
        :type instance: Release DB instance
        :returns: list -- list of all components
        """
        plugin_components = PluginManager.get_components_metadata(instance)
        return instance.components_metadata + plugin_components


class ReleaseCollection(NailgunCollection):
    """Release collection"""

    #: Single Release object class
    single = Release
