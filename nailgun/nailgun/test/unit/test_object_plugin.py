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

from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun import consts
from nailgun.objects import ClusterPlugin
from nailgun.objects import NodeBondInterfaceClusterPlugin
from nailgun.objects import NodeNICInterfaceClusterPlugin
from nailgun.objects import PluginCollection
from nailgun.test import base


class ExtraFunctions(base.BaseTestCase):

    def _create_test_plugins(self):
        for version in ['1.0.0', '2.0.0', '0.0.1', '3.0.0', '4.0.0', '5.0.0']:
            self.env.create_plugin(
                version=version,
                name='multiversion_plugin')
        self.env.create_plugin(
            name='single_plugin')
        self.env.create_plugin(
            name='incompatible_plugin',
            releases=[])

        return [p.id for p in self.env.plugins]

    def _create_test_cluster(self, nodes=[]):
        self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.multinode},
            release_kwargs={
                'name': uuid.uuid4().get_hex(),
                'version': '2015.1-8.0',
                'operating_system': 'Ubuntu',
                'modes': [consts.CLUSTER_MODES.multinode,
                          consts.CLUSTER_MODES.ha_compact]},
            nodes_kwargs=nodes)

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


class TestNodeNICInterfaceClusterPlugin(ExtraFunctions):

    def test_get_all_attributes_by_interface_with_enabled_plugin(self):
        nic_config = self.env.get_default_plugin_nic_config()
        plugin = self.env.create_plugin(
            name='plugin_a_with_nic_attributes',
            nic_attributes_metadata=nic_config)
        cluster = self._create_test_cluster()
        # create node with 1 interface for easy testing
        node = self.env.create_nodes_w_interfaces_count(
            1, 1, **{"cluster_id": cluster.id})[0]
        interface = node.nic_interfaces[0]
        nic_plugin_id = node.node_nic_interface_cluster_plugins[0].id
        ClusterPlugin.set_attributes(cluster.id, plugin.id, enabled=True)

        attributes = NodeNICInterfaceClusterPlugin.\
            get_all_attributes_by_interface(interface)

        self.assertDictEqual({
            'plugin_a_with_nic_attributes': {
                'metadata': {
                    'class': 'plugin',
                    'nic_plugin_id': nic_plugin_id
                },
                'attributes': nic_config
            }
        }, attributes)

    def test_get_all_attributes_by_interface_with_disabled_plugin(self):
        nic_config = self.env.get_default_plugin_nic_config()
        self.env.create_plugin(
            name='plugin_a_with_nic_attributes',
            nic_attributes_metadata=nic_config)
        cluster = self._create_test_cluster()
        node = self.env.create_nodes_w_interfaces_count(
            1, 1, **{"cluster_id": cluster.id})[0]
        interface = node.nic_interfaces[0]

        attributes = NodeNICInterfaceClusterPlugin.\
            get_all_attributes_by_interface(interface)

        self.assertDictEqual({}, attributes)

    def test_populate_nic_with_plugin_attributes(self):
        # create cluster with 2 nodes
        # install plugin with nic attributes which compatible with cluster
        meta = base.reflect_db_metadata()
        nic_config = self.env.get_default_plugin_nic_config()
        self._create_test_cluster(
            nodes=[{'roles': ['controller']}, {'roles': ['compute']}])
        self.env.create_plugin(
            name='plugin_a_with_nic_attributes',
            nic_attributes_metadata=nic_config)

        node_nic_interface_cluster_plugins = self.db.execute(
            meta.tables['node_nic_interface_cluster_plugins'].select()
        ).fetchall()

        self.assertEqual(4, len(node_nic_interface_cluster_plugins))
        for item in node_nic_interface_cluster_plugins:
            self.assertDictEqual(nic_config, jsonutils.loads(item.attributes))

    def test_populate_nic_with_empty_plugin_attributes(self):
        # create cluster with 2 nodes
        # install plugin without nic attributes which compatible with cluster
        meta = base.reflect_db_metadata()
        self._create_test_cluster(
            nodes=[{'roles': ['controller']}, {'roles': ['compute']}])
        self.env.create_plugin(
            name='plugin_b_with_nic_attributes',
            nic_attributes_metadata={})

        node_nic_interface_cluster_plugins = self.db.execute(
            meta.tables['node_nic_interface_cluster_plugins'].select()
        ).fetchall()

        self.assertEqual(0, len(node_nic_interface_cluster_plugins))

    def test_add_cluster_plugin_for_node_nic(self):
        # install plugins compatible with cluster
        # populate cluster with node
        meta = base.reflect_db_metadata()
        nic_config = self.env.get_default_plugin_nic_config()
        self.env.create_plugin(
            name='plugin_a_with_nic_attributes',
            nic_attributes_metadata=nic_config)
        self.env.create_plugin(
            name='plugin_b_with_nic_attributes',
            nic_attributes_metadata={})
        self._create_test_cluster(
            nodes=[{'roles': ['controller']}, {'roles': ['compute']}])

        node_nic_interface_cluster_plugins = self.db.execute(
            meta.tables['node_nic_interface_cluster_plugins'].select()
        ).fetchall()

        self.assertEqual(4, len(node_nic_interface_cluster_plugins))
        for item in node_nic_interface_cluster_plugins:
            self.assertDictEqual(nic_config, jsonutils.loads(item.attributes))

    def test_set_attributes(self):
        meta = base.reflect_db_metadata()
        nic_config = self.env.get_default_plugin_nic_config()
        self.env.create_plugin(
            name='plugin_a_with_nic_attributes',
            nic_attributes_metadata=nic_config)
        cluster = self._create_test_cluster()
        self.env.create_nodes_w_interfaces_count(
            1, 1, **{"cluster_id": cluster.id})[0]

        node_nic_interface_cluster_plugin = self.db.execute(
            meta.tables['node_nic_interface_cluster_plugins'].select()
        ).fetchall()[0]

        _id = node_nic_interface_cluster_plugin.id
        attributes = {'test_attr': 'a'}
        NodeNICInterfaceClusterPlugin.set_attributes(_id, attributes)

        node_nic_interface_cluster_plugin = self.db.execute(
            meta.tables['node_nic_interface_cluster_plugins'].select()
        ).fetchall()[0]

        self.assertDictEqual(
            attributes,
            jsonutils.loads(node_nic_interface_cluster_plugin[1]))


class TestNodeBondInterfaceClusterPlugin(ExtraFunctions):

    def test_set_attributes(self):
        meta = base.reflect_db_metadata()
        bond_config = self.env.get_default_plugin_bond_config()
        self.env.create_plugin(
            name='plugin_a_with_bond_attributes',
            bond_attributes_metadata=bond_config)
        cluster = self._create_test_cluster(
            nodes=[{'roles': ['controller']}])

        for node in cluster.nodes:
            nic_names = [iface.name for iface in node.nic_interfaces]
            self.env.make_bond_via_api(
                'lnx_bond', '', nic_names, node.id,
                bond_properties={'mode': consts.BOND_MODES.balance_rr},
                attrs=bond_config)

        node_bond_interface_cluster_plugin = self.db.execute(
            meta.tables['node_bond_interface_cluster_plugins'].select()
        ).fetchall()[0]

        _id = node_bond_interface_cluster_plugin.id
        attributes = {'test_attr': 'a'}
        NodeBondInterfaceClusterPlugin.set_attributes(_id, attributes)

        node_bond_interface_cluster_plugin = self.db.execute(
            meta.tables['node_bond_interface_cluster_plugins'].select()
        ).fetchall()[0]

        self.assertDictEqual(
            attributes,
            jsonutils.loads(node_bond_interface_cluster_plugin[1]))
