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
from nailgun.objects import PluginCollection
from nailgun.test import base


class TestPluginCollection(base.BaseTestCase):

    def setUp(self):
        super(TestPluginCollection, self).setUp()
        self.release = self.env.create_release(
            version='2015.1-8.0',
            operating_system='Ubuntu',
            modes=[consts.CLUSTER_MODES.ha_compact])
        self.plugin_ids = self._create_test_plugins()

    def test_all_newest(self):
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
        ids = self.plugin_ids[:2]
        plugins = PluginCollection.get_by_uids(ids)
        self.assertEqual(len(list(plugins)), 2)
        self.assertListEqual(
            [plugin.id for plugin in plugins], ids)

    def test_get_all_by_release(self):
        # install 1 plugin compatible with 2015.1-8.0 release
        self.env.create_plugin(
            name='compatible_plugin',
            fuel_version=['8.0'],
            releases=[{
                'repository_path': 'repositories/ubuntu',
                'version': '2015.1-8.0',
                'os': 'ubuntu',
                'mode': ['ha'],
                'deployment_scripts_path': 'deployment_scripts/'}])
        self.assertEqual(len(list(PluginCollection.all())), 6)

        plugins = PluginCollection.get_all_by_release(self.release.id)
        self.assertEqual(len(list(plugins)), 1)
        self.assertEqual(list(plugins)[0]['name'], 'compatible_plugin')
        self.assertEqual(
            list(plugins)[0]['releases'][0]['version'], '2015.1-8.0')

    def _create_test_plugins(self):
        plugin_ids = []
        for version in ['1.0.0', '2.0.0', '0.0.1', '3.0.0']:
            plugin = self.env.create_plugin(
                version=version,
                name='multiversion_plugin')
            plugin_ids.append(plugin.id)

        plugin = self.env.create_plugin(name='single_plugin')
        plugin_ids.append(plugin.id)

        return plugin_ids
