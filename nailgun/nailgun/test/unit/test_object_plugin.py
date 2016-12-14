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

import uuid

import sqlalchemy as sa

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.objects import ClusterPlugin
from nailgun.objects import NodeClusterPlugin
from nailgun.objects import Plugin
from nailgun.objects import PluginCollection
from nailgun.test import base


class ExtraFunctions(base.BaseTestCase):

    def _create_test_plugins(self):
        plugin_ids = []
        for version in ['1.0.0', '2.0.0', '0.0.1', '3.0.0', '4.0.0', '5.0.0']:
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
        return self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.multinode},
            release_kwargs={
                'name': uuid.uuid4().get_hex(),
                'version': '2015.1-8.0',
                'operating_system': 'Ubuntu',
                'modes': [consts.CLUSTER_MODES.multinode,
                          consts.CLUSTER_MODES.ha_compact]})


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

        self.assertEqual(multiversion_plugin[0].version, '5.0.0')

    def test_get_by_uids(self):
        plugin_ids = self._create_test_plugins()
        ids = plugin_ids[:2]
        plugins = PluginCollection.get_by_uids(ids)
        self.assertItemsEqual(ids, (plugin.id for plugin in plugins))

    def test_get_by_release(self):
        release = self.env.create_release(
            version='2015.1-8.0',
            operating_system='Ubuntu',
            modes=[consts.CLUSTER_MODES.ha_compact])
        for plugin in PluginCollection.get_by_release(release):
            self.assertNotEqual(plugin.name, 'incompatible_plugin')


class TestClusterPlugin(ExtraFunctions):

    def test_connect_to_cluster(self):
        meta = base.reflect_db_metadata()
        self._create_test_plugins()
        self._create_test_cluster()
        cluster_plugins = self.db.execute(
            meta.tables['cluster_plugins'].select()
        ).fetchall()
        self.assertEqual(len(cluster_plugins), 7)

    def test_set_plugin_attributes(self):
        meta = base.reflect_db_metadata()
        self._create_test_plugins()
        cluster = self._create_test_cluster()

        plugin = ClusterPlugin.get_connected_plugins(cluster).first()
        ClusterPlugin.set_attributes(cluster.id, plugin.id, enabled=True)

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
            ClusterPlugin.get_connected_plugins_data(cluster.id).count()
        self.assertEqual(7, number_of_connected_plugins_data_items)

    def test_get_all_connected_plugins(self):
        self._create_test_plugins()
        cluster = self._create_test_cluster()
        number_of_connected_plugins =\
            ClusterPlugin.get_connected_plugins(cluster).count()
        self.assertEqual(7, number_of_connected_plugins)

    def test_get_connected_for_specific_plugins(self):
        plugin_ids = self._create_test_plugins()
        cluster = self._create_test_cluster()
        number_of_connected_plugins =\
            ClusterPlugin.get_connected_plugins(
                cluster, plugin_ids[1:]).count()
        self.assertEqual(6, number_of_connected_plugins)

    def test_get_connected_clusters(self):
        plugin_id = self._create_test_plugins()[0]
        for _ in range(2):
            self._create_test_cluster()
        number_of_connected_clusters =\
            ClusterPlugin.get_connected_clusters(plugin_id).count()
        self.assertEqual(2, number_of_connected_clusters)

    def test_get_enabled(self):
        self._create_test_plugins()
        cluster = self._create_test_cluster()

        plugin = ClusterPlugin.get_connected_plugins(cluster).first()
        ClusterPlugin.set_attributes(cluster.id, plugin.id, enabled=True)

        enabled_plugin = ClusterPlugin.get_enabled(cluster.id).first()
        self.assertEqual(plugin.id, enabled_plugin.id)

    def test_is_plugin_used(self):
        self._create_test_plugins()
        cluster = self._create_test_cluster()

        plugin = ClusterPlugin.get_connected_plugins(cluster).first()
        self.assertFalse(ClusterPlugin.is_plugin_used(plugin.id))
        ClusterPlugin.set_attributes(cluster.id, plugin.id, enabled=True)
        self.assertTrue(ClusterPlugin.is_plugin_used(plugin.id))


class TestNodeClusterPlugin(ExtraFunctions):
    def setUp(self):
        super(TestNodeClusterPlugin, self).setUp()
        self.node_attributes = self.env.get_default_plugin_node_config()
        self.cluster = self.env.create(
            release_kwargs={
                'version': 'newton-10.0',
                'operating_system': 'Ubuntu',
            },
            nodes_kwargs=[
                {'role': 'controller'}
            ]
        )
        self.node = self.env.nodes[0]

    def test_get_all_enabled_attributes_by_node(self):
        plugin_b_node_attributes = {
            'plugin_b_section_1': {
                'plugin_b_attr1_key': 'plugin_b_attr1_val',
                'metadata': {'group': 'plugin_group',
                             'label': 'Plugin B Section 1'}
            },
            'plugin_b_section_2': {
                'plugin_b_attr2_key': 'plugin_b_attr2_val',
                'metadata': {'group': 'plugin_group',
                             'label': 'Plugin B Section 2'}
            }
        }
        plugin_a = self.env.create_plugin(
            name='plugin_a_with_node_attributes',
            cluster=self.cluster,
            package_version='5.0.0',
            node_attributes_metadata=self.node_attributes)
        plugin_b = self.env.create_plugin(
            name='plugin_b_with_nic_attributes',
            cluster=self.cluster,
            package_version='5.0.0',
            node_attributes_metadata=plugin_b_node_attributes)

        attributes = NodeClusterPlugin. \
            get_all_enabled_attributes_by_node(self.node)

        node_cluster_plugin_a_id = [
            item.id for item in self.node.node_cluster_plugins if
            item.cluster_plugin_id == plugin_a.cluster_plugins[0].id][0]
        node_cluster_plugin_b_id = [
            item.id for item in self.node.node_cluster_plugins if
            item.cluster_plugin_id == plugin_b.cluster_plugins[0].id][0]

        expected_attributes = self.node_attributes
        expected_attributes.update(plugin_b_node_attributes)
        expected_attributes['plugin_a_section']['metadata'].update({
            'node_plugin_id': node_cluster_plugin_a_id,
            'class': 'plugin'
        })
        expected_attributes['plugin_b_section_1']['metadata'].update({
            'node_plugin_id': node_cluster_plugin_b_id,
            'class': 'plugin'
        })
        expected_attributes['plugin_b_section_2']['metadata'].update({
            'node_plugin_id': node_cluster_plugin_b_id,
            'class': 'plugin'
        })
        self.assertDictEqual(expected_attributes, attributes)

    def test_get_all_enabled_attributes_by_node_with_disabled_plugin(self):
        self.env.create_plugin(
            name='plugin_a_with_node_attributes',
            package_version='5.0.0',
            enabled=False,
            node_attributes_metadata=self.node_attributes)

        attributes = NodeClusterPlugin. \
            get_all_enabled_attributes_by_node(self.node)

        self.assertDictEqual({}, attributes)

    def test_add_cluster_plugins_for_node(self):
        self.env.create_plugin(
            name='plugin_a_with_node_attributes',
            package_version='5.0.0',
            node_attributes_metadata=self.node_attributes)
        self.env.create_plugin(
            name='plugin_b_with_nic_attributes',
            package_version='5.0.0',
            node_attributes_metadata={})
        self.env.create_plugin(
            name='plugin_c_with_nic_attributes',
            package_version='5.0.0',
            node_attributes_metadata=self.node_attributes)

        new_node = self.env.create_node(
            cluster_id=self.cluster.id,
            roles=['compute']
        )
        NodeClusterPlugin.add_cluster_plugins_for_node(new_node)

        self.assertEqual(2, len(new_node.node_cluster_plugins))
        for item in new_node.node_cluster_plugins:
            self.assertDictEqual(self.node_attributes, item.attributes)

    def test_add_nodes_for_cluster_plugin(self):
        meta = base.reflect_db_metadata()
        self.env.create_node(
            cluster_id=self.cluster.id,
            roles=['compute']
        )
        plugin = Plugin.create({
            'name': 'plugin_a_with_node_attributes',
            'title': 'Test Plugin',
            'package_version': '5.0.0',
            'version': '1.0.0',
            'node_attributes_metadata': self.node_attributes
        })
        cluster_plugin = ClusterPlugin.create({
            'cluster_id': self.cluster.id,
            'plugin_id': plugin.id,
            'enabled': False,
            'attributes': self.node_attributes
        })

        NodeClusterPlugin.add_nodes_for_cluster_plugin(cluster_plugin)

        node_cluster_plugins = self.db.execute(
            meta.tables['node_cluster_plugins'].select()
        ).fetchall()

        self.assertEqual(2, len(node_cluster_plugins))
        for item in node_cluster_plugins:
            self.assertDictEqual(self.node_attributes,
                                 jsonutils.loads(item.attributes))

    def test_add_nodes_for_cluster_plugin_with_empty_attributes(self):
        meta = base.reflect_db_metadata()
        self.env.create_node(
            cluster_id=self.cluster.id,
            roles=['compute']
        )
        plugin = Plugin.create({
            'name': 'plugin_a_with_node_attributes',
            'title': 'Test Plugin',
            'package_version': '5.0.0',
            'version': '1.0.0',
            'node_attributes_metadata': {}
        })
        cluster_plugin = ClusterPlugin.create({
            'cluster_id': self.cluster.id,
            'plugin_id': plugin.id,
            'enabled': False,
            'attributes': plugin.node_attributes_metadata
        })

        NodeClusterPlugin.add_nodes_for_cluster_plugin(cluster_plugin)

        node_cluster_plugins = self.db.execute(
            meta.tables['node_cluster_plugins'].select()
        ).fetchall()
        self.assertEqual(0, len(node_cluster_plugins))

    def test_set_attributes(self):
        meta = base.reflect_db_metadata()
        self.env.create_plugin(
            cluster=self.cluster,
            name='plugin_a_with_node_attributes',
            package_version='5.0.0',
            node_attributes_metadata=self.node_attributes)

        node_attributes_cluster_plugin = self.db.execute(
            meta.tables['node_cluster_plugins'].select()
        ).fetchall()[0]

        _id = node_attributes_cluster_plugin.id
        attributes = {'test_attr': 'a'}
        NodeClusterPlugin.set_attributes(_id, attributes)

        node_attributes_cluster_plugin = self.db.execute(
            meta.tables['node_cluster_plugins'].select()
        ).fetchall()[0]

        self.assertDictEqual(
            attributes,
            jsonutils.loads(node_attributes_cluster_plugin[1]))
