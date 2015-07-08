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

from nailgun import objects
#from nailgun.plugins.manager import PluginManager
from nailgun.test import base


class TestPluginManager(base.BaseIntegrationTest):

    def setUp(self):
        super(TestPluginManager, self).setUp()
        self.env.create()
        self.cluster = self.env.clusters[0]
        # Create two plugins
        self.plugins = []
        plugin_volumes_metadata = self.env.get_default_plugin_volumes_config()
        for name in ['test_plugin_1', 'test_plugin_2']:
            plugin_metadata = self.env.get_default_plugin_metadata(
                name=name,
                volumes_metadata=plugin_volumes_metadata
            )
            plugin = objects.Plugin.create(plugin_metadata)
            self.plugins.append((plugin.id, plugin.name))

    def test_get_plugin_volumes_metadata(self):
        print self.plugin_ids
        raise Exception

    def test_sync_plugins_metadata(self):
        pass
