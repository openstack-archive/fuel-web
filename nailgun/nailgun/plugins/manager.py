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
        """Generate Cluster-Plugins relation based on attributes.

        Iterates through plugins attributes, creates
        or deletes Cluster <-> Plugins relation if plugin
        is enabled or disabled.

        :param cluster: A cluster instance
        :type cluster: nailgun.db.sqlalchemy.models.cluster.Cluster
        :param attributes: Cluster attributes
        :type attributes: dict
        """
        plugins = {}

        # Detach plugins data
        for k in list(attributes):
            if cls.is_plugin_data(attributes[k]):
                plugins[k] = attributes.pop(k)['metadata']
                cluster.attributes.editable.pop(k, None)

        for container in six.itervalues(plugins):
            default = container.get('default', False)
            for attrs in container.get('versions', []):
                version_metadata = attrs.pop('metadata')
                plugin_id = version_metadata['plugin_id']
                plugin = Plugin.get_by_uid(plugin_id)
                if not plugin:
                    logger.warning(
                        'Plugin with id "%s" is not found, skip it', plugin_id)
                    continue
                enabled = container['enabled']\
                    and plugin_id == container['chosen_id']
                ClusterPlugins.set_attributes(
                    cluster.id, plugin.id, enabled=enabled,
                    attrs=attrs if enabled or default else None
                )

    @classmethod
    def get_plugins_attributes(
            cls, cluster, all_versions=False, default=False):
        """Gets attributes of all plugins connected with given cluster.

        :param cluster: A cluster instance
        :type cluster: nailgun.db.sqlalchemy.models.cluster.Cluster
        :param all_versions: True to get attributes of all versions of plugins
        :type all_versions: bool
        :param default: True to return a default plugins attributes (for UI)
        :type default: bool
        :return: Plugins attributes
        :rtype: dict
        """
        plugins_attributes = {}
        for plugin in ClusterPlugins.get_connected_plugins_data(cluster.id):
            default_attrs = plugin.attributes_metadata

            if all_versions:
                container = plugins_attributes.setdefault(plugin.name, {})
                enabled = plugin.enabled and not (all_versions and default)
                cls.create_common_metadata(plugin, container, enabled)
                container['metadata']['default'] = default

                versions = container['metadata'].setdefault('versions', [])
                if default:
                    actual_attrs = copy.deepcopy(default_attrs)
                    actual_attrs.setdefault('metadata', {})
                else:
                    actual_attrs = copy.deepcopy(plugin.attributes)
                    actual_attrs['metadata'] = default_attrs.get('metadata',
                                                                 {})
                cls.fill_plugin_metadata(plugin, actual_attrs['metadata'])
                versions.append(actual_attrs)

                container['metadata'].setdefault('chosen_id', plugin.id)
                if enabled:
                    container['metadata']['chosen_id'] = plugin.id

            elif plugin.enabled:
                container = plugins_attributes.setdefault(plugin.name, {})
                cls.create_common_metadata(plugin, container)
                container['metadata'].update(default_attrs.get('metadata', {}))
                cls.fill_plugin_metadata(plugin, container['metadata'])
                container.update(plugin.attributes)

        return plugins_attributes

    @classmethod
    def is_plugin_data(cls, attributes):
        """Looking for a plugins hallmark.

        :param attributes: Item of editable attributes of cluster
        :type attributes: dict
        :return: True if it's a plugins container
        :rtype: bool
        """
        return attributes.get('metadata', {}).get('class') == 'plugin'

    @classmethod
    def create_common_metadata(cls, plugin, attributes, enabled=None):
        """Create common metadata attribute for all versions of plugin.

        :param plugin: A plugin instance
        :type plugin: nailgun.db.sqlalchemy.models.plugins.Plugin
        :param attributes: Common attributes of plugin versions
        :type attributes: dict
        :param enabled: Plugin status
        :type enabled: bool
        """
        metadata = attributes.setdefault('metadata', {
            'class': 'plugin',
            'toggleable': True,
            'weight': 70
        })
        metadata['label'] = plugin.title
        if enabled is None:
            enabled = plugin.enabled
        metadata['enabled'] = enabled or metadata.get('enabled', False)

    @classmethod
    def fill_plugin_metadata(cls, plugin, metadata):
        """Fill a plugin's metadata attribute.

        :param plugin: A plugin instance
        :type plugin: nailgun.db.sqlalchemy.models.plugins.Plugin
        :param metadata: Plugin metadata
        :type metadata: dict
        """
        metadata['plugin_id'] = plugin.id
        metadata['plugin_version'] = plugin.version
        metadata['always_editable'] = plugin.is_hotpluggable

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
            metadata = plugin_adapter.get_metadata()
            Plugin.update(plugin, metadata)

    @classmethod
    def enable_plugins_by_components(cls, cluster):
        """Enable plugin by components.

        :param cluster: A cluster instance
        :type cluster: Cluster model
        """
        cluster_components = set(cluster.components)
        plugin_ids = [p.id for p in PluginCollection.all_newest()]

        for plugin in ClusterPlugins.get_connected_plugins(
                cluster, plugin_ids):
            plugin_adapter = wrap_plugin(plugin)
            plugin_components = set(
                component['name']
                for component in plugin_adapter.components_metadata)

            if cluster_components & plugin_components:
                ClusterPlugins.set_attributes(
                    cluster.id, plugin.id, enabled=True)
