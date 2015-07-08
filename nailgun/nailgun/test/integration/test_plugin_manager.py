# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import mock

from nailgun import objects
from nailgun.plugins.manager import PluginManager
from nailgun.plugins.adapters import PluginAdapterV1
from nailgun.test import base


class TestPluginManager(base.BaseIntegrationTest):

    def setUp(self):
        super(TestPluginManager, self).setUp()
        self.env.create()
        self.cluster = self.env.clusters[0]
        self.plugin_ids = []
        self.plugins_volumes_metadata = []

        # Create two plugins
        for name in ['test_plugin_1', 'test_plugin_2']:
            volumes_metadata = [{'id': name, 'type': 'vg'}]
            plugin_metadata = self.env.get_default_plugin_metadata(
                name=name,
                volumes_metadata=volumes_metadata
            )
            plugin = objects.Plugin.create(plugin_metadata)
            self.cluster.plugins.append(plugin)
            self.plugin_ids.append(plugin.id)
            self.plugins_volumes_metadata.append(volumes_metadata)

    def test_get_plugin_volumes_metadata_for_specific_cluster(self):
        volumes_metadata = PluginManager.get_volumes_metadata(
            self.cluster)
        self.assertEqual(
            volumes_metadata, self.plugins_volumes_metadata)

    @mock.patch.object(PluginAdapterV1, 'sync_metadata_to_db')
    def test_sync_metadata_for_all_plugins(self, sync_mock):
        PluginManager.sync_plugins_metadata()
        self.assertEqual(sync_mock.call_count, 2)

    @mock.patch.object(PluginAdapterV1, 'sync_metadata_to_db')
    def test_sync_metadata_for_specific_plugin(self, sync_mock):
        PluginManager.sync_plugins_metadata(self.plugin_ids[:1])
        self.assertEqual(sync_mock.call_count, 1)
