# -*- coding: utf-8 -*-

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
from nailgun.test import base


class TestPluginCollection(base.BaseTestCase):

    def test_all_newest(self):
        self._create_test_plugins()

        newest_plugins = objects.PluginCollection.all_newest()
        self.assertEqual(len(newest_plugins), 2)

        single_plugin = filter(
            lambda p: p.name == 'single_plugin',
            newest_plugins)
        multiversion_plugin = filter(
            lambda p: p.name == 'multiversion_plugin',
            newest_plugins)

        self.assertEqual(len(single_plugin), 1)
        self.assertEqual(len(multiversion_plugin), 1)

        self.assertEqual(multiversion_plugin[0].version, '3.0.0')

    def test_get_by_uids(self):
        plugin_ids = self._create_test_plugins()
        ids = plugin_ids[:2]
        plugins = objects.PluginCollection.get_by_uids(ids)
        self.assertEqual(len(list(plugins)), 2)
        self.assertListEqual(
            [plugin.id for plugin in plugins], ids)

    def _create_test_plugins(self):
        plugin_ids = []
        for version in ['1.0.0', '2.0.0', '0.0.1', '3.0.0']:
            plugin_data = self.env.get_default_plugin_metadata(
                version=version,
                name='multiversion_plugin')
            plugin = objects.Plugin.create(plugin_data)
            plugin_ids.append(plugin.id)

        single_plugin_data = self.env.get_default_plugin_metadata(
            name='single_plugin')
        plugin = objects.Plugin.create(single_plugin_data)
        plugin_ids.append(plugin.id)

        return plugin_ids
