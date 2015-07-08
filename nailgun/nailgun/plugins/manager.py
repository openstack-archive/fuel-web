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

from nailgun.logger import logger
from nailgun.objects.plugin import Plugin
from nailgun.objects.plugin import PluginCollection
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

        plugin = Plugin.get_by_uid(plugin_id)
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
        for plugin_db in PluginCollection.all_newest():
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

        for plugin in cluster.plugins:
            plugin_adapter = wrap_plugin(plugin)
            metadata = plugin_adapter.volumes_metadata
            # TODO(apopovych): In future we should resolve case when
            # same roles in plugins volumes metadata have different
            # volumes mapping. Now we expect that roles to volumes
            # mapping not cross for different plugins.
            volumes_metadata['volumes_roles_mapping'].update(
                metadata['volumes_roles_mapping'])
            volumes_metadata['volumes'].extend(metadata['volumes'])

        return volumes_metadata

    @classmethod
    def sync_plugins_metadata(cls, plugin_ids=None):
        """Sync metadata for plugins by given ids. If there is not
        ids all newest plugins will be synced
        """
        if plugin_ids:
            plugins = PluginCollection.get_by_uids(plugin_ids)
        else:
            plugins = PluginCollection.all()

        for plugin in plugins:
            plugin_adapter = wrap_plugin(plugin)
            plugin_adapter.sync_metadata_to_db()

    @classmethod
    def get_plugins_deployment_tasks(cls, cluster):
        deployment_tasks = []

        for plugin_db in cluster.plugins:
            plugin_adapter = wrap_plugin(plugin_db)
            deployment_tasks.extend(plugin_adapter.deployment_tasks)

        return deployment_tasks

    @classmethod
    def get_plugins_node_roles(cls, cluster):
        node_roles = {}

        for plugin_db in cluster.plugins:
            roles_metadata = plugin_db.roles_metadata

            if set(roles_metadata) & set(node_roles):
                logger.warning(
                    "Plugin (ID=%s) is unable to register the following "
                    "node roles: %s".format(
                        plugin_db.id,
                        ", ".join(set(roles_metadata) & set(node_roles))))
                continue

            node_roles.update(roles_metadata)

        return node_roles
