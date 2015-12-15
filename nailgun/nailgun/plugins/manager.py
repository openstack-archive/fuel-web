#    Copyright 2014 Mirantis, Inc.
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

import copy
import six
from six.moves import map

from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.objects.plugin import ClusterPlugins
from nailgun.objects.plugin import Plugin
from nailgun.objects.plugin import PluginCollection
from nailgun.plugins.adapters import wrap_plugin


class PluginManager(object):

    @classmethod
    def process_cluster_attributes(cls, cluster, attributes):
        """Generate Cluster-Plugins relation based on attributes

        Iterates through plugins attributes, creates
        or deletes Cluster <-> Plugins relation if plugin
        is enabled or disabled.

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        :param attributes: Cluster attributes
        :type attributes: dict
        """
        def _convert_attrs(plugin_id, attrs):
            prefix = "#{0}_".format(plugin_id)
            result = dict((title[len(prefix):], attrs[title])
                          for title in attrs
                          if title.startswith(prefix))
            for attr in six.itervalues(result):
                if 'restrictions' not in attr:
                    continue
                if len(attr['restrictions']) == 1:
                    attr.pop('restrictions')
                else:
                    attr['restrictions'].pop()
            return result

        for attrs in six.itervalues(attributes):
            if not isinstance(attrs, dict):
                continue

            plugin_versions = attrs.pop('plugin_versions', None)
            if plugin_versions is None:
                continue

            metadata = attrs.pop('metadata', {})
            plugin_enabled = metadata.get('enabled', False)
            default = metadata.get('default', False)

            for version in plugin_versions['values']:
                pid = version.get('data')
                plugin = Plugin.get_by_uid(pid)
                if not plugin:
                    logger.warning(
                        'Plugin with id "%s" is not found, skip it', pid)
                    continue

                enabled = plugin_enabled and\
                    pid == plugin_versions['value']

                ClusterPlugins.set_attributes(
                    cluster.id, plugin.id, enabled=enabled,
                    attrs=_convert_attrs(plugin.id, attrs)
                    if enabled or default else None
                )

    @classmethod
    def get_plugins_attributes(
            cls, cluster, all_versions=False, default=False):
        """Gets attributes of all plugins connected with given cluster.

        :param cluster: A cluster instance
        :type cluster: nailgun.objects.cluster.Cluster
        :param all_versions: True to get attributes of all versions of plugins
        :type all_versions: bool
        :param default: True to return a default plugins attributes (for UI)
        :type default: bool
        :return: Plugins attributes
        :rtype: dict
        """
        versions = {
            'type': 'radio',
            'values': [],
            'weight': 10,
            'value': None,
            'label': 'Choose a plugin version'
        }

        plugins_attributes = {}
        for plugin in ClusterPlugins.get_connected_plugins_data(cluster.id):
            plugin_id = str(plugin.id)
            enabled = plugin.enabled and not (all_versions and default)
            plugin_attributes = plugins_attributes.setdefault(plugin.name, {})
            metadata = plugin_attributes.setdefault('metadata', {
                'toggleable': True,
                'weight': 70
            })
            metadata['enabled'] = enabled or metadata.get('enabled', False)
            metadata['label'] = plugin.title
            if plugin.is_hotpluggable:
                metadata["always_editable"] = True

            if all_versions:
                metadata['default'] = default

                plugin_attributes.update(
                    cls.convert_plugin_attributes(
                        plugin,
                        plugin.attributes_metadata
                        if default else plugin.attributes
                    )
                )

                plugin_version = {
                    'data': plugin_id,
                    'description': '',
                    'label': plugin.version,
                }
                if not plugin.is_hotpluggable:
                    plugin_version['restrictions'] = [{
                        'action': 'disable',
                        'condition': 'cluster:is_locked'
                    }]

                plugin_versions = plugin_attributes.get('plugin_versions')
                if plugin_versions is not None:
                    if enabled:
                        plugin_versions['value'] = plugin_id
                else:
                    plugin_versions = copy.deepcopy(versions)
                    plugin_versions['value'] = plugin_id
                    plugin_attributes['plugin_versions'] = plugin_versions

                plugin_versions['values'].append(plugin_version)
            elif enabled:
                plugin_attributes.update(plugin.attributes)

        return plugins_attributes

    @classmethod
    def convert_plugin_attributes(cls, plugin, attributes):
        def converter(plugin_id, plugin_name, title, attr):
            restrictions = attr.setdefault('restrictions', [])
            restrictions.append({
                'action': 'hide',
                'condition': "settings:{0}.plugin_versions.value != '{1}'"
                .format(plugin_name, plugin_id)
            })
            return "#{0}_{1}".format(plugin_id, title), attr

        return (
            converter(plugin.id, plugin.name, k, v)
            for k, v in six.iteritems(attributes)
        )

    @classmethod
    def get_cluster_plugins_with_tasks(cls, cluster):
        cluster_plugins = []
        for plugin_db in ClusterPlugins.get_enabled(cluster.id):
            plugin_adapter = wrap_plugin(plugin_db)
            plugin_adapter.set_cluster_tasks()
            cluster_plugins.append(plugin_adapter)
        return cluster_plugins

    @classmethod
    def get_network_roles(cls, cluster, merge_policy):
        """Returns the network roles from plugins.

        The roles cluster and plugins will be mixed
        according to merge policy.
        """

        instance_roles = cluster.release.network_roles_metadata
        all_roles = dict((role['id'], role) for role in instance_roles)
        conflict_roles = dict()

        for plugin in ClusterPlugins.get_enabled(cluster.id):
            for role in plugin.network_roles_metadata:
                role_id = role['id']
                if role_id in all_roles:
                    try:
                        merge_policy.apply_patch(
                            all_roles[role_id],
                            role
                        )
                    except errors.UnresolvableConflict as e:
                        logger.error("cannot merge plugin {0}: {1}"
                                     .format(plugin.name, e))
                        conflict_roles[role_id] = plugin.name
                else:
                    all_roles[role_id] = role

        if conflict_roles:
            raise errors.NetworkRoleConflict(
                "Cannot override existing network roles: '{0}' in "
                "plugins: '{1}'".format(
                    ', '.join(conflict_roles),
                    ', '.join(set(conflict_roles.values()))))

        return list(all_roles.values())

    @classmethod
    def get_plugins_deployment_tasks(cls, cluster):
        deployment_tasks = []
        processed_tasks = {}

        enabled_plugins = ClusterPlugins.get_enabled(cluster.id)
        for plugin_adapter in map(wrap_plugin, enabled_plugins):
            depl_tasks = plugin_adapter.deployment_tasks

            for t in depl_tasks:
                t_id = t['id']
                if t_id in processed_tasks:
                    raise errors.AlreadyExists(
                        'Plugin {0} is overlapping with plugin {1} '
                        'by introducing the same deployment task with '
                        'id {2}'
                        .format(plugin_adapter.full_name,
                                processed_tasks[t_id],
                                t_id)
                    )
                processed_tasks[t_id] = plugin_adapter.full_name

            deployment_tasks.extend(depl_tasks)

        return deployment_tasks

    @classmethod
    def get_plugins_node_roles(cls, cluster):
        result = {}
        core_roles = set(cluster.release.roles_metadata)

        for plugin_db in ClusterPlugins.get_enabled(cluster.id):
            plugin_roles = wrap_plugin(plugin_db).normalized_roles_metadata

            # we should check all possible cases of roles intersection
            # with core ones and those from other plugins
            # and afterwards show them in error message;
            # thus role names for which following checks
            # fails are accumulated in err_info variable
            err_roles = set(
                r for r in plugin_roles if r in core_roles or r in result
            )
            if err_roles:
                raise errors.AlreadyExists(
                    "Plugin (ID={0}) is unable to register the following "
                    "node roles: {1}".format(plugin_db.id,
                                             ", ".join(sorted(err_roles)))
                )

            # update info on processed roles in case of
            # success of all intersection checks
            result.update(plugin_roles)

        return result

    @classmethod
    def get_volumes_metadata(cls, cluster):
        """Get volumes metadata for cluster from all plugins which enabled it.

        :param cluster: A cluster instance
        :type cluster: Cluster model
        :return: dict -- Object with merged volumes data from plugins
        """
        volumes_metadata = {
            'volumes': [],
            'volumes_roles_mapping': {}
        }
        release_volumes = cluster.release.volumes_metadata.get('volumes', [])
        release_volumes_ids = [v['id'] for v in release_volumes]
        processed_volumes = {}

        enabled_plugins = ClusterPlugins.get_enabled(cluster.id)
        for plugin_adapter in map(wrap_plugin, enabled_plugins):
            metadata = plugin_adapter.volumes_metadata

            for volume in metadata.get('volumes', []):
                volume_id = volume['id']
                if volume_id in release_volumes_ids:
                    raise errors.AlreadyExists(
                        'Plugin {0} is overlapping with release '
                        'by introducing the same volume with id "{1}"'
                        .format(plugin_adapter.full_name, volume_id))
                elif volume_id in processed_volumes:
                    raise errors.AlreadyExists(
                        'Plugin {0} is overlapping with plugin {1} '
                        'by introducing the same volume with id "{2}"'
                        .format(plugin_adapter.full_name,
                                processed_volumes[volume_id],
                                volume_id))

                processed_volumes[volume_id] = plugin_adapter.full_name

            volumes_metadata.get('volumes_roles_mapping', {}).update(
                metadata.get('volumes_roles_mapping', {}))
            volumes_metadata.get('volumes', []).extend(
                metadata.get('volumes', []))

        return volumes_metadata

    @classmethod
    def get_components_metadata(cls, release):
        """Get components metadata for all plugins which related to release.

        :param release: A release instance
        :type release: Release model
        :return: list -- List of plugins components
        """
        components = []
        seen_components = \
            dict((c['name'], 'release') for c in release.components_metadata)

        for plugin_adapter in map(
                wrap_plugin, PluginCollection.get_by_release(release)):
            plugin_name = plugin_adapter.name
            for component in plugin_adapter.components_metadata:
                name = component['name']
                if seen_components.get(name, plugin_name) != plugin_name:
                    raise errors.AlreadyExists(
                        'Plugin {0} is overlapping with {1} by introducing '
                        'the same component with name "{2}"'
                        .format(plugin_adapter.name,
                                seen_components[name],
                                name))

                if name not in seen_components:
                    seen_components[name] = plugin_adapter.name
                    components.append(component)

        return components

    @classmethod
    def sync_plugins_metadata(cls, plugin_ids=None):
        """Sync metadata for plugins by given IDs.

        If there are no IDs, all newest plugins will be synced.

        :param plugin_ids: list of plugin IDs
        :type plugin_ids: list
        """
        if plugin_ids:
            plugins = PluginCollection.get_by_uids(plugin_ids)
        else:
            plugins = PluginCollection.all()

        for plugin in plugins:
            plugin_adapter = wrap_plugin(plugin)
            plugin_adapter.sync_metadata_to_db()

    @classmethod
    def enable_plugins_by_components(cls, cluster):
        """Enable plugin by components

        :param cluster: A cluster instance
        :type cluster: Cluster model
        :return: None
        """
        cluster_components = set(cluster.components)
        plugin_ids = set(p.id for p in PluginCollection.all_newest())

        for plugin in ClusterPlugins.get_connected_plugins(
                cluster, plugin_ids):
            plugin_adapter = wrap_plugin(plugin)
            plugin_components = set(
                component['name']
                for component in plugin_adapter.components_metadata)

            for component in cluster_components & plugin_components:
                ClusterPlugins.set_attributes(
                    cluster.id, plugin.id, enabled=True)
