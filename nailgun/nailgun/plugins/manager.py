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

from nailgun.objects.plugin import PluginCollection

from nailgun.plugins import plugin


class PluginManager(object):

    @classmethod
    def process_cluster_attributes(cls, cluster, attrs, query=None):
        if query is None:
            query = PluginCollection.all()
        for plugin_db in query:
            attr_plugin = plugin.ClusterAttributesPlugin(plugin_db)
            attr_plugin.process_cluster_attributes(cluster, attrs)

    @classmethod
    def upload_plugin_attributes(cls, cluster):
        plugins_attrs = {}
        for plugin_db in PluginCollection.all():
            attr_plugin = plugin.ClusterAttributesPlugin(plugin)
            attrs = attr_plugin.upload_plugin_attributes(cluster)
            plugins_attrs.update(attrs)
        return plugins_attrs

    @classmethod
    def get_cluster_tasks(cls, cluster, query=None):
        if query is None:
            query = PluginCollection.all()
        tasks = []
        for plugin_db in query:
            attr_plugin = plugin.ClusterAttributesPlugin(plugin)
            tasks.extend(attr_plugin.get_cluster_tasks(cluster))
        return tasks
