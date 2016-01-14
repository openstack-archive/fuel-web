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
from nailgun.objects import ClusterPlugins
from nailgun.objects import Plugin
from nailgun.objects import PluginCollection
from nailgun.test import base
import sqlalchemy as sa
import uuid


class ExtraFunctions(base.BaseTestCase):

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

        incompatible_plugin_data = self.env.get_default_plugin_metadata(
            name='incompatible_plugin',
            releases=[]
        )
        plugin = Plugin.create(incompatible_plugin_data)
        plugin_ids.append(plugin.id)

        return plugin_ids

    def _create_test_cluster(self):
        self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.multinode},
            release_kwargs={
                'name': uuid.uuid4().get_hex(),
                'version': 'liberty-8.0',
                'operating_system': 'Ubuntu',
                'modes': [consts.CLUSTER_MODES.multinode,
                          consts.CLUSTER_MODES.ha_compact]})

        return self.env.clusters[0]


class TestPluginCollection(ExtraFunctions):

    def test_all_newest(self):
        self._create_test_plugins()

        newest_plugins = PluginCollection.all_newest()
        self.assertEqual(len(newest_plugins), 3)

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

    def test_get_by_release(self):
        release = self.env.create_release(
            version='liberty-8.0',
            operating_system='Ubuntu',
            modes=[consts.CLUSTER_MODES.ha_compact])
        for plugin in PluginCollection.get_by_release(release):
            self.assertNotEqual(plugin.name, 'incompatible_plugin')


class TestClusterPlugins(ExtraFunctions):

    def test_connect_to_cluster(self):
        meta = base.reflect_db_metadata()
        self._create_test_plugins()
        self._create_test_cluster()
        cluster_plugins = self.db.execute(
            meta.tables['cluster_plugins'].select()
        ).fetchall()
        self.assertEqual(len(cluster_plugins), 5)

    def test_set_plugin_attributes(self):
        meta = base.reflect_db_metadata()
        self._create_test_plugins()
        cluster = self._create_test_cluster()

        plugin = ClusterPlugins.get_connected_plugins(cluster).first()
        ClusterPlugins.set_attributes(cluster.id, plugin.id, enabled=True)

        columns = meta.tables['cluster_plugins'].c
        enabled = self.db.execute(
            sa.select([columns.enabled])
            .where(columns.cluster_id == cluster.id)
            .where(columns.plugin_id == plugin.id)
        ).fetchone()
        self.assertTrue(enabled[0])

    def test_get_connected_plugins_data(self):
        self._create_test_plugins()
        cluster = self._create_test_cluster()
        number_of_connected_plugins_data_items =\
            ClusterPlugins.get_connected_plugins_data(cluster.id).count()
        self.assertEqual(5, number_of_connected_plugins_data_items)

    def test_get_all_connected_plugins(self):
        self._create_test_plugins()
        cluster = self._create_test_cluster()
        number_of_connected_plugins =\
            ClusterPlugins.get_connected_plugins(cluster).count()
        self.assertEqual(5, number_of_connected_plugins)

    def test_get_connected_for_specific_plugins(self):
        plugin_ids = self._create_test_plugins()
        cluster = self._create_test_cluster()
        number_of_connected_plugins =\
            ClusterPlugins.get_connected_plugins(
                cluster, plugin_ids[1:]).count()
        self.assertEqual(4, number_of_connected_plugins)

    def test_get_connected_clusters(self):
        plugin_id = self._create_test_plugins()[0]
        for _ in range(2):
            self._create_test_cluster()
        number_of_connected_clusters =\
            ClusterPlugins.get_connected_clusters(plugin_id).count()
        self.assertEqual(2, number_of_connected_clusters)

    def test_get_enabled(self):
        self._create_test_plugins()
        cluster = self._create_test_cluster()

        plugin = ClusterPlugins.get_connected_plugins(cluster).first()
        ClusterPlugins.set_attributes(cluster.id, plugin.id, enabled=True)

        enabled_plugin = ClusterPlugins.get_enabled(cluster.id).first()
        self.assertEqual(plugin.id, enabled_plugin.id)

    def test_is_plugin_used(self):
        self._create_test_plugins()
        cluster = self._create_test_cluster()

        plugin = ClusterPlugins.get_connected_plugins(cluster).first()
        self.assertFalse(ClusterPlugins.is_plugin_used(plugin.id))
        ClusterPlugins.set_attributes(cluster.id, plugin.id, enabled=True)
        self.assertTrue(ClusterPlugins.is_plugin_used(plugin.id))
