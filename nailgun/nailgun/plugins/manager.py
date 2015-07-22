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

import six
from six.moves import map

from nailgun.errors import errors
from nailgun.logger import logger
from nailgun import objects
from nailgun.plugins.adapters import wrap_plugin


class PluginManager(object):

    @classmethod
    def process_cluster_attributes(cls, cluster, attrs):
        """Iterates through plugins attributes, creates
        or deletes Cluster <-> Plugins relation if plugin
        is enabled or disabled.

        :param cluster: Cluster object
        :param attrs: dictionary with cluster attributes
        """
        for key, attr in six.iteritems(attrs):
            cls._process_attr(cluster, attr)

    @classmethod
    def _process_attr(cls, cluster, attr):
        if not isinstance(attr, dict):
            return

        metadata = attr.get('metadata', {})
        plugin_id = metadata.get('plugin_id')

        if not plugin_id:
            return

        plugin = objects.Plugin.get_by_uid(plugin_id)
        if not plugin:
            logger.warning('Plugin with id "%s" is not found, skip it',
                           plugin_id)
            return

        enabled = metadata.get('enabled', False)

        # Value is true and plugin is not enabled for this cluster
        # that means plugin was enabled on this request
        if enabled and cluster not in plugin.clusters:
            plugin.clusters.append(cluster)
        # Value is false and plugin is enabled for this cluster
        # that means plugin was disabled on this request
        elif not enabled and cluster in plugin.clusters:
            plugin.clusters.remove(cluster)

    @classmethod
    def get_plugin_attributes(cls, cluster):
        plugin_attributes = {}
        for plugin_db in objects.PluginCollection.all_newest():
            plugin_adapter = wrap_plugin(plugin_db)
            attributes = plugin_adapter.get_plugin_attributes(cluster)
            plugin_attributes.update(attributes)
        return plugin_attributes

    @classmethod
    def get_cluster_plugins_with_tasks(cls, cluster):
        cluster_plugins = []
        for plugin_db in cluster.plugins:
            plugin_adapter = wrap_plugin(plugin_db)
            plugin_adapter.set_cluster_tasks()
            cluster_plugins.append(plugin_adapter)
        return cluster_plugins

    @classmethod
    def get_network_roles(cls, cluster):
        core_roles = cluster.release.network_roles_metadata
        known_roles = set(role['id'] for role in core_roles)

        plugin_roles = []
        conflict_roles = {}
        for plugin in cluster.plugins:
            for role in plugin.network_roles_metadata:
                role_id = role['id']
                if role_id in known_roles:
                    conflict_roles[role_id] = plugin.name
                known_roles.add(role_id)
            plugin_roles.extend(plugin.network_roles_metadata)

        if conflict_roles:
            raise errors.NetworkRoleConflict(
                "Cannot override existing network roles: '{0}' in "
                "plugins: '{1}'".format(
                    ', '.join(conflict_roles),
                    ', '.join(set(conflict_roles.values()))))

        return plugin_roles

    @classmethod
    def get_plugins_deployment_tasks(cls, cluster):
        deployment_tasks = []

        processed_tasks = {}
        for plugin_adapter in map(wrap_plugin, cluster.plugins):
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

        for plugin_db in cluster.plugins:
            plugin_roles = plugin_db.roles_metadata

            # we should check all possible cases of roles intersection
            # with core ones and those from other plugins
            # and afterwards show them in error message;
            # thus role names for which following checks
            # fails are accumulated in err_info variable
            err_roles = set()
            if set(plugin_roles) & core_roles:
                err_roles |= set(plugin_roles) & core_roles
            if set(plugin_roles) & set(result):
                err_roles |= set(plugin_roles) & set(result)

            if err_roles:
                raise errors.AlreadyExists(
                    "Plugin (ID={0}) is unable to register the following "
                    "node roles: {1}".format(plugin_db.id,
                                             ", ".join(err_roles))
                )

            # update info on processed roles in case of
            # success of all intersection checks
            result.update(plugin_roles)

        return result

    @classmethod
    def get_volumes_metadata(cls, cluster):
        """Get volumes metadata for specific cluster from all
        plugins which enabled for it.

        :param cluster: Cluster DB model
        :returns: dict -- object with merged volumes data from plugins
        """
        volumes_metadata = {
            'volumes': [],
            'volumes_roles_mapping': {}
        }
        release_volumes = cluster.release.volumes_metadata.get('volumes', [])
        release_volumes_ids = [v['id'] for v in release_volumes]
        processed_volumes = {}

        for plugin_adapter in map(wrap_plugin, cluster.plugins):
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
    def sync_plugins_metadata(cls, plugin_ids=None):
        """Sync metadata for plugins by given ids. If there is not
        ids all newest plugins will be synced
        """
        if plugin_ids:
            plugins = objects.PluginCollection.get_by_uids(plugin_ids)
        else:
            plugins = objects.PluginCollection.all()

        for plugin in plugins:
            plugin_adapter = wrap_plugin(plugin)
            plugin_adapter.sync_metadata_to_db()
