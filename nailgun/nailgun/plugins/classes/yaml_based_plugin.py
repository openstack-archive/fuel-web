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

import os

from nailgun.settings import settings

from nailgun.plugins.classes.base import NailgunPlugin


class YamlBasedPlugin(NailgunPlugin):

    def __init__(self, plugin):
        self.plugin = plugin
        plugin_version = '{0}-{1}'.format(plugin.name, plugin.version)
        config_file = os.path.join(
            settings.BASE_PLUGIN_DIR,
            plugin_version,
            'environment_config.yaml')
        super(NailgunPlugin, self).__init__(plugin.name, config_file)

    def upload_plugin_attributes(self, cluster):
        """Should be used for initial configuration uploading to
            custom storage. Will be invoked in 2 cases:
            1. Cluster is created but there was no plugins in system
            on that time, so when plugin is uploaded we need to iterate
            over all clusters and decide if plugin should be applied
            2. Plugins is uploaded before cluster creation, in this case
            we will iterate over all plugins and upload configuration for them
        """
        if self.config:
            attrs = self.config.pop("attributes", {})
            with self.storage as storage:
                storage.add_record(
                    "cluster_attribute",
                    {"attributes": {self.plugin_name: attrs},
                     "cluster_id": cluster.id})

    def process_cluster_attributes(self, cluster, cluster_attrs):
        custom_attrs = cluster_attrs.pop(self.plugin_name, {})
        with self.storage as storage:
            storage.add_record(
                "cluster_attribute",
                {"attributes": {self.plugin_name: custom_attrs},
                 "cluster_id": cluster.id}
            )
        if custom_attrs:
            value = custom_attrs['metadata']['enabled']
            # value is true and plugin is not enabled for this cluster
            # that means plugin was enabled on this request
            if value and cluster not in self.plugin.clusters:
                self.plugin.clusters.add(cluster)
            # value is false and plugin is enabled for this cluster
            # that means plugin was disabled on this request
            elif not value and cluster in self.plugin.clusters:
                self.plugin.clusters.delete(cluster)

    def get_cluster_attributes(self, cluster):
        return self.storage.search_records(
            'cluster_attribute',
            cluster_id=cluster.id)['attributes']
