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
import itertools

import six
import yaml

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import DeploymentGraph
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
        # process graphs
        graphs = {}
        graphs_list = data.pop('graphs', [])
        for graph in graphs_list:
            graphs[graph.pop('type')] = graph

        deployment_tasks = data.pop("deployment_tasks", [])

        if not graphs.get(consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE):
            graphs[consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE] = \
                {'tasks': deployment_tasks}

        release_obj = super(Release, cls).create(data)

        for graph_type, graph_data in six.iteritems(graphs):
            DeploymentGraph.create_for_model(
                graph_data, release_obj, graph_type)

        return release_obj

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

        graphs = {}
        graphs_list = data.pop('graphs', [])
        for graph in graphs_list:
            graphs[graph.pop('type')] = graph
        deployment_tasks = data.pop("deployment_tasks", [])

        existing_default_graph = DeploymentGraph.get_for_model(
            instance, consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE)

        if (existing_default_graph and len(deployment_tasks)) \
                or not existing_default_graph:
            graphs[consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE] = \
                {'tasks': deployment_tasks}
        release_obj = super(Release, cls).update(instance, data)

        for graph_type, graph_data in six.iteritems(graphs):
            g = DeploymentGraph.get_for_model(instance, graph_type)
            if g:
                DeploymentGraph.update(g, graph_data)
            else:
                DeploymentGraph.create_for_model(
                    graph_data, instance, graph_type)

        return release_obj

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
        # notify about changes
        instance.volumes_metadata.changed()

    @classmethod
    def remove_role(cls, instance, role_name):
        result = instance.roles_metadata.pop(role_name, None)
        instance.volumes_metadata['volumes_roles_mapping'].pop(role_name, None)
        # notify about changes
        instance.volumes_metadata.changed()
        return bool(result)

    @classmethod
    def update_tag(cls, instance, tag):
        """Update existing Release instance with specified tag.

        Previous ones are deleted.

        :param instance: a Release instance
        :param tag: a tag dict
        :returns: None
        """
        instance.tags_metadata[tag['name']] = tag['meta']

    @classmethod
    def remove_tag(cls, instance, tag_name):
        from nailgun.objects import Cluster
        cls.remove_tag_from_roles(instance, tag_name)
        res = instance.tags_metadata.pop(tag_name, None)
        for cluster in instance.clusters:
            if tag_name not in cluster.tags_metadata:
                Cluster.remove_tag_from_roles(cluster, tag_name)
                Cluster.remove_primary_tag(cluster, tag_name)
        db().flush()
        return bool(res)

    @classmethod
    def remove_tag_from_roles(cls, instance, tag_name):
        for role, meta in six.iteritems(cls.get_own_roles(instance)):
            tags = meta.get('tags', [])
            if tag_name in tags:
                tags.remove(tag_name)
                instance.roles_metadata.changed()

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
    def is_lcm_supported(cls, instance):
        """Check if LCM is available for release

        :param instance: a Release instance
        :returns: boolean
        """
        return (
            StrictVersion(instance.environment_version) >=
            StrictVersion(consts.FUEL_LCM_AVAILABLE)
        )

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
    def is_nfv_supported(cls, instance):
        """Check if nfv features are available for release

        :param instance: a Release instance
        :return: boolean
        """
        return (StrictVersion(instance.environment_version)
                >= StrictVersion(consts.FUEL_NFV_AVAILABLE_SINCE))

    @classmethod
    def get_volumes_metadata(cls, instance):
        return instance.volumes_metadata

    @classmethod
    def get_deployment_graph(cls, instance, graph_type=None):
        """Get deployment graph based on release version.

        :param instance: Release instance
        :type instance: models.Release
        :param graph_type: deployment graph type
        :type graph_type: basestring|None
        :returns: list of deployment tasks
        :rtype: list
        """
        if graph_type is None:
            graph_type = consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE

        env_version = instance.environment_version

        deployment_graph = DeploymentGraph.get_for_model(instance, graph_type)
        if deployment_graph:
            deployment_tasks = DeploymentGraph.get_tasks(deployment_graph)
        else:
            # deployment tasks list should always be returned
            deployment_tasks = []

        if graph_type == consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE and \
                not deployment_tasks:
            # upload default legacy graphs
            if env_version.startswith('5.0'):
                deployment_tasks = yaml.load(
                    graph_configuration.DEPLOYMENT_50)
            elif env_version.startswith('5.1') \
                    or env_version.startswith('6.0'):
                deployment_tasks = yaml.load(
                    graph_configuration.DEPLOYMENT_51_60)

            if deployment_graph:
                if deployment_tasks:
                    DeploymentGraph.update(
                        deployment_graph, {'tasks': deployment_tasks})
            else:
                # create graph anyway
                deployment_graph = DeploymentGraph.create_for_model(
                    {'tasks': deployment_tasks}, instance)

        if deployment_graph:
            metadata = DeploymentGraph.get_metadata(deployment_graph)
        else:
            metadata = {}

        metadata['tasks'] = deployment_tasks
        return metadata

    @classmethod
    def get_deployment_tasks(cls, instance, graph_type=None):
        """Gets deployment tasks from release related graph."""
        return cls.get_deployment_graph(instance, graph_type)['tasks']

    @classmethod
    def get_min_controller_count(cls, instance):
        return instance.roles_metadata['controller']['limits']['min']

    @classmethod
    def get_all_components(cls, instance):
        """Get all components related to release

        Due to components architecture compatible/incompatible are duplex
        relations. So if some component is compatible/incompatible with another
        the last one also should have such relation.

        :param instance: Release instance
        :type instance: Release DB instance
        :returns: list -- list of all components
        """
        plugin_components = PluginManager.get_components_metadata(instance)
        components = copy.deepcopy(
            instance.components_metadata + plugin_components)
        # we should provide commutative property for compatible/incompatible
        # relations between components
        for comp_i, comp_j in itertools.permutations(components, 2):
            if cls._check_relation(comp_j, comp_i, 'incompatible'):
                comp_i.setdefault('incompatible', []).append({
                    'name': comp_j['name'],
                    'message': "Not compatible with {0}".format(
                        comp_j.get('label') or comp_j.get('name'))})
            if cls._check_relation(comp_j, comp_i, 'compatible'):
                comp_i.setdefault('compatible', []).append({
                    'name': comp_j['name']})

        return components

    @classmethod
    def get_node_by_role(cls, instance, role_name):
        from objects import Node
        cluster_ids = db().query(models.Cluster.id).filter_by(
            release_id=instance.id
        ).subquery()
        return Node.get_nodes_by_role(cluster_ids, role_name).first()

    @classmethod
    def get_roles(cls, instance):
        return instance.roles_metadata

    @classmethod
    def get_own_roles(cls, instance):
        return instance.roles_metadata

    @classmethod
    def get_tags_metadata(cls, instance):
        return cls.get_own_tags(instance)

    @classmethod
    def get_own_tags(cls, instance):
        return instance.tags_metadata

    @classmethod
    def _check_relation(cls, a, b, relation):
        """Helper function to check commutative property for relations"""
        return (cls._contain(a.get(relation, []), b['name']) and not
                cls._contain(b.get(relation, []), a['name']))

    @staticmethod
    def _contain(components, name):
        """Check if component with given name exists in components list

        :param components: list of components objects(dicts)
        :type components: list
        :param name: component name or wildcard
        :type name: string
        """
        prefixes = (comp['name'].split('*', 1)[0] for comp in components)
        return any(name.startswith(x) for x in prefixes)

    @classmethod
    def get_supported_dpdk_drivers(cls, instance):
        """Get all supported DPDK drivers

        Returns dictionary, where keys are names of supported drivers and
        values are lists of supported device IDs for each driver.

        :param instance: Release instance
        :return: supported DPDK drivers and devices
        """
        metadata = instance.networks_metadata
        return metadata.get('dpdk_drivers', {})

    @classmethod
    def delete(cls, instance):
        """Delete release.

        :param instance: Release model instance
        :type instance: models.Release
        """
        DeploymentGraph.delete_for_parent(instance)
        super(Release, cls).delete(instance)


class ReleaseCollection(NailgunCollection):
    """Release collection"""

    #: Single Release object class
    single = Release
