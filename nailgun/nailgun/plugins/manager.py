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
from nailgun.plugins.attr_plugin import wrap_plugin


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
        plugins_attrs = {}
        for plugin_db in PluginCollection.all_newest():
            attr_plugin = wrap_plugin(plugin_db)
            attrs = attr_plugin.get_plugin_attributes(cluster)
            plugins_attrs.update(attrs)
        return plugins_attrs

    @classmethod
    def get_cluster_plugins_with_tasks(cls, cluster):
        attr_plugins = []
        for plugin_db in cluster.plugins:
            attr_pl = wrap_plugin(plugin_db)
            attr_pl.set_cluster_tasks(cluster)
            attr_plugins.append(attr_pl)
        return attr_plugins

    @classmethod
    def sync_plugins_metadata(cls, plugin_ids):
        if plugin_ids:
            plugins = [Plugin.get_by_uid(uid) for uid in plugin_ids]
        else:
            plugins = PluginCollection.all_newest()

        for plugin in plugins:
            plugin_wrapper = wrap_plugin(plugin)
            plugin_wrapper.sync_metadata_to_db()
