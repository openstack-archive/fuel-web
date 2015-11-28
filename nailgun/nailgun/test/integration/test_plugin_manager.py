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
import uuid

from nailgun import consts
from nailgun.errors import errors
from nailgun.objects import ClusterPlugins
from nailgun.plugins.adapters import PluginAdapterV3
from nailgun.plugins.manager import PluginManager
from nailgun.test import base


class TestPluginManager(base.BaseIntegrationTest):

    def setUp(self):
        super(TestPluginManager, self).setUp()
        self.env.create(
            release_kwargs={
                'version': '2015.1-8.0',
                'operating_system': 'Ubuntu'})

        self.release = self.env.releases[0]
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

    def test_get_components_metadata(self):
        self.env.create_plugin(
            name='plugin_with_components',
            package_version='4.0.0',
            fuel_version=['8.0'],
            components_metadata=self.env.get_default_components())

        components_metadata = PluginManager.get_components_metadata(
            self.release)
        self.assertEqual(
            components_metadata, self.env.get_default_components())

    def test_raise_exception_when_plugin_overlap_release_component(self):
        release = self.env.create_release(
            version='2015.1-8.1',
            operating_system='Ubuntu',
            modes=[consts.CLUSTER_MODES.ha_compact],
            components_metadata=self.env.get_default_components())

        self.env.create_plugin(
            name='plugin_with_components',
            package_version='4.0.0',
            fuel_version=['8.0'],
            releases=[{
                'repository_path': 'repositories/ubuntu',
                'version': '2015.1-8.1', 'os': 'ubuntu',
                'mode': ['ha'],
                'deployment_scripts_path': 'deployment_scripts/'}],
            components_metadata=self.env.get_default_components())

        expected_message = (
            'Plugin plugin_with_components-0.1.0 is overlapping with release '
            'by introducing the same component with name '
            '"hypervisor:test_hypervisor"')

        with self.assertRaisesRegexp(errors.AlreadyExists,
                                     expected_message):
            PluginManager.get_components_metadata(release)

    def test_raise_exception_when_plugin_overlap_another_component(self):
        self.env.create_plugin(
            name='plugin_with_components_1',
            package_version='4.0.0',
            fuel_version=['8.0'],
            components_metadata=self.env.get_default_components())

        self.env.create_plugin(
            name='plugin_with_components_2',
            package_version='4.0.0',
            fuel_version=['8.0'],
            components_metadata=self.env.get_default_components())

        expected_message = (
            'Plugin plugin_with_components_2-0.1.0 is overlapping with '
            'plugin_with_components_1-0.1.0 by introducing the same component '
            'with name "hypervisor:test_hypervisor"')

        with self.assertRaisesRegexp(errors.AlreadyExists,
                                     expected_message):
            PluginManager.get_components_metadata(self.release)

    def test_enable_plugins_by_component(self):
        self.env.create_plugin(
            name='plugin_with_test_storage',
            package_version='4.0.0',
            fuel_version=['8.0'],
            releases=[{
                'repository_path': 'repositories/ubuntu',
                'version': '2015.1-8.3',
                'os': 'ubuntu',
                'mode': ['ha'],
                'deployment_scripts_path': 'deployment_scripts/'}],
            components_metadata=self.env.get_default_components(
                name='storage:test_storage'))

        plugin = self.env.create_plugin(
            version='1.0.0',
            name='plugin_with_test_storage',
            package_version='4.0.0',
            fuel_version=['8.0'],
            releases=[{
                'repository_path': 'repositories/ubuntu',
                'version': '2015.1-8.3',
                'os': 'ubuntu',
                'mode': ['ha'],
                'deployment_scripts_path': 'deployment_scripts/'}],
            components_metadata=self.env.get_default_components(
                name='storage:test_storage'))

        cluster = self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': '2015.1-8.3'},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'api': False,
                'components': [
                    'hypervisor:test_hypervisor',
                    'storage:test_storage']})

        enabled_plugins = ClusterPlugins.get_enabled(cluster.id)
        self.assertItemsEqual([plugin], enabled_plugins)

    def test_get_plugins_attributes_when_cluster_is_locked(self):
        self.env.create(api=False)
        cluster = self.env.clusters[-1]
        plugin_a1 = self.env.create_plugin(
            name='plugin_a', version='1.0.1',
            cluster=cluster, enabled=False
        )
        plugin_a2 = self.env.create_plugin(
            name='plugin_a', version='1.0.2', is_hotpluggable=True,
            cluster=cluster, enabled=False
        )
        plugin_b = self.env.create_plugin(
            name='plugin_b', title='plugin_a_title', cluster=cluster
        )
        cluster.status = consts.CLUSTER_STATUSES.operational
        self.db.flush()
        self.assertTrue(cluster.is_locked)
        attributes = PluginManager.get_plugins_attributes(
            cluster, all_versions=True, default=True
        )

        pl_a1 = attributes['plugin_a']['metadata']['versions'][0]
        pl_a2 = attributes['plugin_a']['metadata']['versions'][1]
        pl_b = attributes['plugin_b']['metadata']['versions'][0]

        self.assertItemsEqual(['plugin_a', 'plugin_b'], attributes)
        self.assertItemsEqual(
            {
                'plugin_id': plugin_a1.id,
                'plugin_version': plugin_a1.version,
                'restrictions': [
                    {
                        'action': 'disable',
                        'condition': 'cluster:is_locked'
                    }
                ]
            }, pl_a1['metadata']
        )
        self.assertItemsEqual(
            {
                'plugin_id': plugin_a2.id,
                'plugin_version': plugin_a2.version,
                'always_editable': True,
            },
            pl_a2['metadata']
        )
        self.assertItemsEqual(
            {
                'plugin_id': plugin_b.id,
                'plugin_version': plugin_b.version,
                'restrictions': [
                    {
                        'action': 'disable',
                        'condition': 'cluster:is_locked'
                    }
                ]
            }, pl_b['metadata']
        )
        self.assertEqual(
            plugin_a1.id,
            attributes['plugin_a']['metadata']['chosen_id']
        )
        self.assertEqual(
            plugin_b.id,
            attributes['plugin_b']['metadata']['chosen_id']
        )

    def test_get_plugins_attributes_when_cluster_is_not_locked(self):
        self.env.create(api=False)
        cluster = self.env.clusters[-1]
        plugin_a1 = self.env.create_plugin(
            name='plugin_a', version='1.0.1',
            cluster=cluster, enabled=False
        )
        plugin_a2 = self.env.create_plugin(
            name='plugin_a', version='1.0.2', is_hotpluggable=True,
            cluster=cluster, enabled=True
        )
        plugin_b = self.env.create_plugin(
            name='plugin_b', title='plugin_a_title', cluster=cluster
        )
        self.assertFalse(plugin_a1.is_hotpluggable)
        self.assertTrue(plugin_a2.is_hotpluggable)
        self.assertFalse(plugin_b.is_hotpluggable)
        self.assertFalse(cluster.is_locked)
        attributes = PluginManager.get_plugins_attributes(
            cluster, all_versions=True, default=True
        )

        pl_a1 = attributes['plugin_a']['metadata']['versions'][0]
        pl_a2 = attributes['plugin_a']['metadata']['versions'][1]
        pl_b = attributes['plugin_b']['metadata']['versions'][0]

        self.assertItemsEqual(['plugin_a', 'plugin_b'], attributes)

        self.assertItemsEqual(
            {
                'plugin_id': plugin_a1.id,
                'plugin_version': plugin_a1.version,
                'restrictions': [
                    {
                        'action': 'disable',
                        'condition': 'cluster:is_locked'
                    }
                ]
            }, pl_a1['metadata']
        )
        self.assertItemsEqual(
            {
                'plugin_id': plugin_a2.id,
                'plugin_version': plugin_a2.version,
                'always_editable': True,
            },
            pl_a2['metadata']
        )
        self.assertItemsEqual(
            {
                'plugin_id': plugin_b.id,
                'plugin_version': plugin_b.version,
                'restrictions': [
                    {
                        'action': 'disable',
                        'condition': 'cluster:is_locked'
                    }
                ]
            }, pl_b['metadata']
        )
        self.assertEqual(
            plugin_a1.id,
            attributes['plugin_a']['metadata']['chosen_id']
        )
        self.assertEqual(
            plugin_b.id,
            attributes['plugin_b']['metadata']['chosen_id']
        )


class TestClusterPluginIntegration(base.BaseTestCase):

    _compat_meta = {
        'releases': [{
            'os': 'ubuntu',
            'mode': 'ha',
            'version': '2015.1-8.0',
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
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': '2015.1-8.0'},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
            })
        self.cluster = self.env.clusters[0]

    def _create_plugin(self, **kwargs):
        plugin = self.env.create_plugin(name=uuid.uuid4().get_hex(), **kwargs)
        return plugin

    def test_get_compatible_plugins(self):
        plugin_a = self._create_plugin(**self._compat_meta)
        self._create_plugin(**self._uncompat_meta)

        compat_plugins = ClusterPlugins.get_compatible_plugins(self.cluster)
        self.assertItemsEqual(compat_plugins, [plugin_a])

    def test_get_compatible_plugins_for_new_cluster(self):
        plugin_a = self._create_plugin(**self._compat_meta)
        plugin_b = self._create_plugin(**self._compat_meta)
        self._create_plugin(**self._uncompat_meta)

        self.env.create(
            cluster_kwargs={
                'release_id': self.cluster.release.id,
                'mode': consts.CLUSTER_MODES.ha_compact,
            })
        cluster = self.env.clusters[1]

        compat_plugins = ClusterPlugins.get_compatible_plugins(cluster)
        self.assertItemsEqual(compat_plugins, [plugin_a, plugin_b])

    def test_get_enabled_plugins(self):
        plugin_a = self._create_plugin(**self._compat_meta)
        plugin_b = self._create_plugin(**self._compat_meta)

        ClusterPlugins.set_attributes(
            self.cluster.id, plugin_a.id, enabled=True)

        compat_plugins = ClusterPlugins.get_compatible_plugins(self.cluster)
        self.assertItemsEqual(compat_plugins, [plugin_a, plugin_b])

        enabled_plugins = ClusterPlugins.get_enabled(self.cluster.id)
        self.assertItemsEqual(enabled_plugins, [plugin_a])
