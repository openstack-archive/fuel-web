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

from nailgun import consts
from nailgun.objects import Plugin
from nailgun.objects import PluginCollection
from nailgun.test import base


class TestPluginCollection(base.BaseTestCase):

    def setUp(self):
        super(TestPluginCollection, self).setUp()
        self.release = self.env.create_release(
            version='2015.1-8.0',
            operating_system='Ubuntu',
            modes=[consts.CLUSTER_MODES.ha_compact])

    def test_all_newest(self):
        self._create_test_plugins()

        newest_plugins = PluginCollection.all_newest()
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
        plugins = PluginCollection.get_by_uids(ids)
        self.assertEqual(len(list(plugins)), 2)
        self.assertListEqual(
            [plugin.id for plugin in plugins], ids)

    def test_get_all_by_release(self):
        # install 5 plugins (4 multiversion and 1 single)
        self._create_test_plugins()
        plugin_data = self.env.get_default_plugin_metadata(
            name='compatible_plugin',
            releases=[{
                'repository_path': 'repositories/ubuntu',
                'version': '2015.1-8.0',
                'os': 'ubuntu',
                'mode': ['ha'],
                'deployment_scripts_path': 'deployment_scripts/'}])
        # install 1 plugin compatible with 2015.1-8.0 release
        Plugin.create(plugin_data)
        self.assertEqual(len(list(PluginCollection.all())), 6)

        plugins = PluginCollection.get_all_by_release(self.release.id)
        self.assertEqual(len(list(plugins)), 1)
        self.assertEqual(list(plugins)[0]['name'], 'compatible_plugin')
        self.assertEqual(
            list(plugins)[0]['releases'][0]['version'], '2015.1-8.0')

    def _create_test_plugins(self):
        plugin_ids = []
        for version in ['1.0.0', '2.0.0', '0.0.1', '3.0.0']:
            plugin_data = self.env.get_default_plugin_metadata(
                version=version,
                name='multiversion_plugin')
            plugin = Plugin.create(plugin_data)
            plugin_ids.append(plugin.id)

        single_plugin_data = self.env.get_default_plugin_metadata(
            name='single_plugin')
        plugin = Plugin.create(single_plugin_data)
        plugin_ids.append(plugin.id)

        return plugin_ids
