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

from nailgun import objects

from nailgun.plugins import plugin


class PluginManager(object):

    @classmethod
    def process_cluster_attributes(cls, cluster, attrs, query=None):
        if query is None:
            query = objects.PluginCollection.all()
        for plugin_db in query:
            attr_plugin = plugin.ClusterAttributesPlugin(plugin_db)
            attr_plugin.process_cluster_attributes(cluster, attrs)

    @classmethod
    def upload_plugin_attributes(cls, cluster):
        for plugin_db in objects.PluginCollection.all():
            attr_plugin = plugin.ClusterAttributesPlugin(plugin)
            attr_plugin.upload_plugin_attributes(cluster)

    @classmethod
    def get_cluster_tasks(cls, cluster, query=None):
        if query is None:
            query = objects.PluginCollection.all()
        tasks = []
        for plugin_db in query:
            attr_plugin = plugin.ClusterAttributesPlugin(plugin)
            tasks.extend(attr_plugin.get_cluster_tasks(cluster))
        return tasks
