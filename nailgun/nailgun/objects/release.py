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

import copy

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
        # mark sqlalchemy's attribute as dirty, so it will be flushed
        # when needed
        instance.roles_metadata = copy.deepcopy(instance.roles_metadata)
        instance.volumes_metadata = copy.deepcopy(instance.volumes_metadata)

        instance.roles_metadata[role['name']] = role['meta']
        instance.volumes_metadata['volumes_roles_mapping'][role['name']] = \
            role.get('volumes_roles_mapping', [])

    @classmethod
    def remove_role(cls, instance, role_name):
        # mark sqlalchemy's attribute as dirty, so it will be flushed
        # when needed
        instance.roles_metadata = copy.deepcopy(instance.roles_metadata)
        instance.volumes_metadata = copy.deepcopy(instance.volumes_metadata)

        result = instance.roles_metadata.pop(role_name, None)
        instance.volumes_metadata['volumes_roles_mapping'].pop(role_name, None)
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

        Due to components architecture compatible/incompatible are duplex
        relations. So if some component compatible/incompatible with another
        the last one also should have such relation.

        :param instance: Release instance
        :type instance: Release DB instance
        :returns: list -- list of all components
        """
        plugin_components = PluginManager.get_components_metadata(instance)
        components = instance.components_metadata + plugin_components

        for component in components:
            for incompatible_item in component.get('incompatible', []):
                incompatible_components = cls._find_components(
                    incompatible_item['name'], components)

                if incompatible_components:
                    for incompatible_component in incompatible_components:
                        incompatible_component.setdefault('incompatible', [])
                        incompatible_names = set(
                            item['name']
                            for item in incompatible_component['incompatible'])

                        if component['name'] not in incompatible_names:
                            incompatible_component['incompatible'].append({
                                'name': component['name'],
                                'message': 'Not compatible with {0}'.format(
                                    component.get('label'))
                            })

            for compatible_item in component.get('compatible', []):
                compatible_components = cls._find_components(
                    compatible_item['name'], components)

                if compatible_components:
                    for compatible_component in compatible_components:
                        compatible_component.setdefault('compatible', [])
                        compatible_names = set(
                            item['name']
                            for item in compatible_component['compatible'])

                        if component['name'] not in compatible_names:
                            compatible_component['compatible'].append({
                                'name': component['name']})

        return components

    @staticmethod
    def _find_components(name, components):
        """Find proper components by name or wildcard

        Example:
            find_components('component_name', components_list)
            find_components('component_type:*', components_list)

        :param name: component name or wildcard
        :type name: string
        :param components: list of components objects(dicts)
        :type components: list
        :returns: generator of components objects
        """
        prefix = name.split('*', 1)[0]
        return (component for component in components
                if component['name'].startswith(prefix))


class ReleaseCollection(NailgunCollection):
    """Release collection"""

    #: Single Release object class
    single = Release
