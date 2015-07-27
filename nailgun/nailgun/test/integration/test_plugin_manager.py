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

import uuid

import mock

from nailgun.errors import errors
from nailgun import objects
from nailgun.plugins.adapters import PluginAdapterV3
from nailgun.plugins.manager import PluginManager
from nailgun.test import base


class TestPluginManager(base.BaseIntegrationTest):

    def setUp(self):
        super(TestPluginManager, self).setUp()
        self.env.create()
        self.cluster = self.env.clusters[0]

        # Create two plugins with package verion 3.0.0
        for name in ['test_plugin_1', 'test_plugin_2']:
            volumes_metadata = {
                'volumes_roles_mapping': {
                    name: [{'allocate_size': 'min', 'id': name}]
                },
                'volumes': [{'id': name, 'type': 'vg'}]
            }
            self.env.create_plugin(
                api=True,
                cluster=self.cluster,
                name=name,
                package_version='3.0.0',
                fuel_version=['7.0'],
                volumes_metadata=volumes_metadata
            )

    def test_get_plugin_volumes_metadata_for_cluster(self):
        volumes_metadata = PluginManager.get_volumes_metadata(
            self.cluster)
        expected_volumes_metadata = {
            'volumes_roles_mapping': {
                'test_plugin_1': [
                    {'allocate_size': 'min', 'id': 'test_plugin_1'}
                ],
                'test_plugin_2': [
                    {'allocate_size': 'min', 'id': 'test_plugin_2'}
                ],
            },
            'volumes': [
                {'id': 'test_plugin_1', 'type': 'vg'},
                {'id': 'test_plugin_2', 'type': 'vg'}
            ]
        }

        self.assertEqual(
            volumes_metadata['volumes_roles_mapping'],
            expected_volumes_metadata['volumes_roles_mapping'])
        self.assertItemsEqual(
            volumes_metadata['volumes'],
            expected_volumes_metadata['volumes'])

    def test_get_empty_plugin_volumes_metadata_for_cluster(self):
        cluster = self.env.create_cluster(api=False)
        self.env.create_plugin(
            api=True,
            cluster=cluster,
            package_version='3.0.0',
            fuel_version=['7.0']
        )
        volumes_metadata = PluginManager.get_volumes_metadata(cluster)
        expected_volumes_metadata = {
            'volumes_roles_mapping': {}, 'volumes': []}

        self.assertEqual(
            volumes_metadata, expected_volumes_metadata)

    def test_raise_exception_when_plugin_overlap_release_volumes(self):
        cluster = self.env.create_cluster(api=False)
        plugin_name = 'test_plugin_3'
        volumes_metadata = {
            'volumes_roles_mapping': {
                plugin_name: [
                    {'allocate_size': 'min', 'id': plugin_name}
                ]
            },
            'volumes': [
                {'id': 'os', 'type': 'vg'},
                {'id': plugin_name, 'type': 'vg'}
            ]
        }
        self.env.create_plugin(
            api=True,
            cluster=cluster,
            name=plugin_name,
            package_version='3.0.0',
            fuel_version=['7.0'],
            volumes_metadata=volumes_metadata
        )

        expected_message = (
            'Plugin test_plugin_3-0.1.0 is overlapping with release '
            'by introducing the same volume with id "os"')

        with self.assertRaisesRegexp(errors.AlreadyExists,
                                     expected_message):
            PluginManager.get_volumes_metadata(cluster)

    def test_raise_exception_when_plugin_overlap_another_plugin_volumes(self):
        plugin_name = 'test_plugin_4'
        volumes_metadata = {
            'volumes_roles_mapping': {
                plugin_name: [
                    {'allocate_size': 'min', 'id': plugin_name}
                ]
            },
            'volumes': [
                {'id': 'test_plugin_2', 'type': 'vg'},
                {'id': plugin_name, 'type': 'vg'}
            ]
        }
        self.env.create_plugin(
            api=True,
            cluster=self.cluster,
            name=plugin_name,
            package_version='3.0.0',
            fuel_version=['7.0'],
            volumes_metadata=volumes_metadata
        )

        expected_message = (
            'Plugin test_plugin_4-0.1.0 is overlapping with plugin '
            'test_plugin_2-0.1.0 by introducing the same volume '
            'with id "test_plugin_2"')

        with self.assertRaisesRegexp(errors.AlreadyExists,
                                     expected_message):
            PluginManager.get_volumes_metadata(self.cluster)

    @mock.patch.object(PluginAdapterV3, 'sync_metadata_to_db')
    def test_sync_metadata_for_all_plugins(self, sync_mock):
        PluginManager.sync_plugins_metadata()
        self.assertEqual(sync_mock.call_count, 2)

    @mock.patch.object(PluginAdapterV3, 'sync_metadata_to_db')
    def test_sync_metadata_for_specific_plugin(self, sync_mock):
        PluginManager.sync_plugins_metadata([self.env.plugins[0].id])
        self.assertEqual(sync_mock.call_count, 1)


class TestClusterPluginIntegration(base.BaseTestCase):

    _compat_meta = {
        'releases': [{
            'os': 'ubuntu',
            'mode': 'ha',
            'version': '2014.2-6.1',
        }]
    }

    _uncompat_meta = {
        'releases': [{
            'os': 'ubuntu',
            'mode': 'ha',
            'version': '2014.2-7.0',
        }]
    }

    def setUp(self):
        super(TestClusterPluginIntegration, self).setUp()

        self.env.create(
            release_kwargs={
                'operating_system': 'ubuntu',
                'version': '2014.2-6.1'},
            cluster_kwargs={
                'mode': 'ha_compact',
            })
        self.cluster = self.env.clusters[0]

    def create_plugin(self, **kwargs):
        plugin = objects.Plugin.create(self.env.get_default_plugin_metadata(
            name=uuid.uuid4().get_hex(),
            **kwargs
        ))
        self.db.flush()
        return plugin

    def test_get_compatible_plugins(self):
        plugin_a = self.create_plugin(**self._compat_meta)
        self.create_plugin(**self._uncompat_meta)

        compat_plugins = PluginManager.get_compatible_plugins(self.cluster)
        self.assertItemsEqual(compat_plugins, [plugin_a])

    def test_get_enabled_plugins(self):
        plugin_a = self.create_plugin(**self._compat_meta)
        plugin_b = self.create_plugin(**self._compat_meta)

        objects.Plugin.set_enabled(plugin_a, self.cluster, enabled=True)

        compat_plugins = PluginManager.get_compatible_plugins(self.cluster)
        self.assertItemsEqual(compat_plugins, [plugin_a, plugin_b])

        enabled_plugins = PluginManager.get_enabled_plugins(self.cluster)
        self.assertItemsEqual(enabled_plugins, [plugin_a])

    def test_get_compatible_plugins_for_new_cluster(self):
        plugin_a = self.create_plugin(**self._compat_meta)
        plugin_b = self.create_plugin(**self._compat_meta)
        self.create_plugin(**self._uncompat_meta)

        self.env.create(
            cluster_kwargs={
                'release_id': self.cluster.release.id,
                'mode': 'ha_compact',
            })
        cluster = self.env.clusters[1]

        compat_plugins = PluginManager.get_compatible_plugins(cluster)
        self.assertItemsEqual(compat_plugins, [plugin_a, plugin_b])
