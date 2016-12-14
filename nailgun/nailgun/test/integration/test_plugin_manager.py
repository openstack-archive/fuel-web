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
from nailgun import errors
from nailgun.objects import ClusterPlugin
from nailgun.plugins.adapters import PluginAdapterV3
from nailgun.plugins.manager import PluginManager
from nailgun.test import base


class TestPluginManager(base.BaseIntegrationTest):

    def setUp(self):
        super(TestPluginManager, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={
                'version': '2015.1-8.0',
                'operating_system': 'Ubuntu'})

        self.release = self.env.releases[0]

        # Create two plugins with package verion 3.0.0
        for name in ['test_plugin_1', 'test_plugin_2']:
            volumes_metadata = {
                'volumes_roles_mapping': {
                    name: [{'allocate_size': 'min', 'id': name}]
                },
                'volumes': [{'id': name, 'type': 'vg'}]
            }
            self.env.create_plugin(
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

    def test_plugin_role_with_empty_tags(self):
        role_name = 'test'
        roles_meta = {
            role_name: {
                'has_primary': True,
                'tags': []
            }
        }
        plugin = self.env.create_plugin(
            cluster=self.cluster,
            package_version='3.0.0',
            roles_metadata=roles_meta
        )
        self.assertEqual(
            plugin.roles_metadata[role_name]['tags'], [])

    def test_plugin_legacy_tags(self):
        role_name = 'test'
        roles_meta = {
            role_name: {
                'has_primary': True
            }
        }
        plugin = self.env.create_plugin(
            cluster=self.cluster,
            package_version='3.0.0',
            roles_metadata=roles_meta
        )
        self.assertEqual(
            plugin.roles_metadata[role_name]['tags'], [role_name])
        self.assertEqual(
            plugin.tags_metadata[role_name]['has_primary'],
            roles_meta[role_name]['has_primary'])

    def test_get_empty_plugin_volumes_metadata_for_cluster(self):
        cluster = self.env.create_cluster(api=False)
        self.env.create_plugin(
            cluster=cluster,
            package_version='3.0.0'
        )
        volumes_metadata = PluginManager.get_volumes_metadata(cluster)
        expected_volumes_metadata = {
            'volumes_roles_mapping': {}, 'volumes': [],
            'rule_to_pick_boot_disk': []}

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

    @mock.patch.object(PluginManager, '_list_plugins_on_fs')
    @mock.patch.object(PluginAdapterV3, 'get_metadata')
    def test_sync_metadata_for_all_plugins(self, sync_mock, list_fs_m):
        list_fs_m.return_value = ['test_plugin_1-0.1', 'test_plugin_2-0.1']
        PluginManager.sync_plugins_metadata()
        self.assertEqual(sync_mock.call_count, 2)

    @mock.patch.object(PluginAdapterV3, 'get_metadata')
    def test_sync_metadata_for_specific_plugin(self, sync_mock):
        PluginManager.sync_plugins_metadata([self.env.plugins[0].id])
        self.assertEqual(sync_mock.call_count, 1)

    def test_get_components(self):
        self.env.create_plugin(
            name='plugin_with_components',
            package_version='4.0.0',
            fuel_version=['8.0'],
            components_metadata=self.env.get_default_components())

        components_metadata = PluginManager.get_components_metadata(
            self.release)
        self.assertEqual(
            components_metadata, self.env.get_default_components())

    def test_get_components_for_same_plugins_with_different_verions(self):
        self.env.create_plugin(
            name='plugin_with_components_to_test_verions',
            package_version='4.0.0',
            fuel_version=['8.0'],
            components_metadata=self.env.get_default_components())

        self.env.create_plugin(
            name='plugin_with_components_to_test_verions',
            version='1.0.0',
            package_version='4.0.0',
            fuel_version=['8.0'],
            components_metadata=self.env.get_default_components())

        # PluginManager should return only one component for same plugin
        # but different versions
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
            'Plugin plugin_with_components is overlapping with release '
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
            'Plugin plugin_with_components_2 is overlapping with '
            'plugin_with_components_1 by introducing the same component '
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

        enabled_plugins = ClusterPlugin.get_enabled(cluster.id)
        self.assertItemsEqual([plugin], enabled_plugins)

    def test_get_plugins_attributes_when_cluster_is_locked(self):
        cluster = self.env.create(api=False)
        plugin_a1 = self.env.create_plugin(
            name='plugin_a', version='1.0.1',
            cluster=cluster, enabled=False
        )
        plugin_a2 = self.env.create_plugin(
            name='plugin_a', version='1.0.2', is_hotpluggable=True,
            cluster=cluster, enabled=False
        )
        plugin_b = self.env.create_plugin(
            name='plugin_b', title='plugin_a_title', cluster=cluster,
            attributes_metadata={
                'attributes': {
                    'metadata': {
                        'restrictions': [
                            {
                                "condition": "test_condition",
                                "action": "hide"
                            }
                        ]
                    }
                }
            }
        )
        cluster.status = consts.CLUSTER_STATUSES.operational
        self.db.flush()
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
                'hot_pluggable': False,
                'contains_legacy_tasks': False
            }, pl_a1['metadata']
        )
        self.assertItemsEqual(
            {
                'plugin_id': plugin_a2.id,
                'plugin_version': plugin_a2.version,
                'hot_pluggable': True,
                'contains_legacy_tasks': False
            },
            pl_a2['metadata']
        )
        self.assertItemsEqual(
            {
                'plugin_id': plugin_b.id,
                'plugin_version': plugin_b.version,
                'hot_pluggable': False,
                'contains_legacy_tasks': False,
                'restrictions': [
                    {
                        "condition": "cluster:net_provider != 'neutron'",
                        "action": "hide"
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
        cluster = self.env.create(api=False)
        plugin_a1 = self.env.create_plugin(
            name='plugin_a', version='1.0.1',
            cluster=cluster, enabled=False
        )
        plugin_a2 = self.env.create_plugin(
            name='plugin_a', version='1.0.2', is_hotpluggable=True,
            cluster=cluster, enabled=True
        )
        plugin_b = self.env.create_plugin(
            name='plugin_b', title='plugin_a_title', cluster=cluster,
            attributes_metadata={
                'attributes': {
                    'metadata': {
                        'restrictions': [
                            {
                                "condition": "test_condition",
                                "action": "hide"
                            }
                        ]
                    }
                }
            }
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
                'hot_pluggable': False,
                'contains_legacy_tasks': False
            }, pl_a1['metadata']
        )
        self.assertItemsEqual(
            {
                'plugin_id': plugin_a2.id,
                'plugin_version': plugin_a2.version,
                'hot_pluggable': True,
                'contains_legacy_tasks': False
            },
            pl_a2['metadata']
        )
        self.assertItemsEqual(
            {
                'plugin_id': plugin_b.id,
                'plugin_version': plugin_b.version,
                'hot_pluggable': False,
                'contains_legacy_tasks': False,
                'restrictions': [
                    {
                        "condition": "cluster:net_provider != 'neutron'",
                        "action": "hide"
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

    def test_merge_plugin_values(self):
        attributes = {
            'test_plugin': {
                'metadata': {
                    'class': 'plugin',
                    'chosen_id': 1,
                    'enabled': True,
                    'versions': [
                        {
                            'metadata': {
                                'plugin_id': 1
                            },
                            'attribute_a': {
                                'value': 'test_a'
                            },
                            'attribute_b': {
                                'value': 'test_b'
                            }
                        },
                        {
                            'metadata': {
                                'plugin_id': 2
                            },
                            'attribute_a': {
                                'value': 'test_a'
                            },
                            'attribute_c': {
                                'value': 'test_c'
                            }
                        }
                    ]
                },
                'attribute_a': {'value': ''},
                'attribute_b': {'value': ''}
            }
        }

        PluginManager.inject_plugin_attribute_values(attributes)

        self.assertEqual(
            'test_a', attributes['test_plugin']['attribute_a']['value'])
        self.assertEqual(
            'test_b', attributes['test_plugin']['attribute_b']['value'])

    def test_get_specific_version(self):
        versions = [
            {'metadata': {'plugin_id': '1'}},
            {'metadata': {'plugin_id': '2'}}
        ]

        plugin_version_attrs = PluginManager._get_specific_version(
            versions, '1')
        self.assertEqual(versions[0], plugin_version_attrs)
        not_existed_plugin_version_attrs = PluginManager._get_specific_version(
            versions, '3')
        self.assertEqual({}, not_existed_plugin_version_attrs)


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

        self.cluster = self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': '2015.1-8.0'},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
            })

    def _create_plugin(self, **kwargs):
        plugin = self.env.create_plugin(name=uuid.uuid4().get_hex(), **kwargs)
        return plugin

    def test_get_compatible_plugins(self):
        plugin_a = self._create_plugin(**self._compat_meta)
        self._create_plugin(**self._uncompat_meta)

        compat_plugins = ClusterPlugin.get_compatible_plugins(self.cluster)
        self.assertItemsEqual(compat_plugins, [plugin_a])

    def test_get_compatible_plugins_for_new_cluster(self):
        plugin_a = self._create_plugin(**self._compat_meta)
        plugin_b = self._create_plugin(**self._compat_meta)
        self._create_plugin(**self._uncompat_meta)

        cluster = self.env.create(
            cluster_kwargs={
                'release_id': self.cluster.release.id,
                'mode': consts.CLUSTER_MODES.ha_compact,
            })

        compat_plugins = ClusterPlugin.get_compatible_plugins(cluster)
        self.assertItemsEqual(compat_plugins, [plugin_a, plugin_b])

    def test_get_enabled_plugins(self):
        plugin_a = self._create_plugin(**self._compat_meta)
        plugin_b = self._create_plugin(**self._compat_meta)

        ClusterPlugin.set_attributes(
            self.cluster.id, plugin_a.id, enabled=True)

        compat_plugins = ClusterPlugin.get_compatible_plugins(self.cluster)
        self.assertItemsEqual(compat_plugins, [plugin_a, plugin_b])

        enabled_plugins = ClusterPlugin.get_enabled(self.cluster.id)
        self.assertItemsEqual(enabled_plugins, [plugin_a])


class TestNodeClusterPluginIntegration(base.BaseTestCase):

    def setUp(self):
        super(TestNodeClusterPluginIntegration, self).setUp()

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
        self.plugin = self.env.create_plugin(
            name='plugin_a',
            cluster=self.cluster,
            package_version='5.0.0',
            enabled=True,
            title='Plugin A Title',
            node_attributes_metadata={
                'plugin_a_section_1': {
                    'metadata': {'label': 'Section 1 of Plugin A'},
                    'attr_1': {'value': 'test_1'}
                },
                'plugin_a_section_2': {
                    'attr_2': {'value': 'test_2'}
                }
            })

    def test_get_node_default_attributes(self):
        self.env.create_plugin(
            name='plugin_b',
            cluster=self.cluster,
            enabled=True,
            package_version='5.0.0',
            node_attributes_metadata={
                'section_plugin_b': {
                    'attr_b': {'value': 'test_b'}
                }
            })

        self.env.create_plugin(
            name='plugin_c',
            cluster=self.cluster,
            enabled=False,
            package_version='5.0.0',
            node_attributes_metadata={
                'plugin_c_section': {
                    'attr_c': {'value': 'test_c'}
                }
            })

        for node_cluster_plugin in self.cluster.nodes[0].node_cluster_plugins:
            node_cluster_plugin.attributes = {}
        self.db.flush()

        default_attributes = PluginManager.get_plugins_node_default_attributes(
            self.cluster)
        self.assertDictEqual(
            {
                'plugin_a_section_1': {
                    'metadata': {'label': 'Section 1 of Plugin A'},
                    'attr_1': {'value': 'test_1'}},
                'plugin_a_section_2': {
                    'attr_2': {'value': 'test_2'}},
                'section_plugin_b': {
                    'attr_b': {'value': 'test_b'}}
            },
            default_attributes
        )

    def test_get_plugin_node_attributes(self):
        attributes = PluginManager.get_plugin_node_attributes(self.node)
        del attributes['plugin_a_section_1']['metadata']['node_plugin_id']
        del attributes['plugin_a_section_2']['metadata']['node_plugin_id']
        self.assertDictEqual(
            {
                'plugin_a_section_1': {
                    'metadata': {'label': 'Section 1 of Plugin A',
                                 'class': 'plugin'},
                    'attr_1': {'value': 'test_1'}},
                'plugin_a_section_2': {
                    'metadata': {'class': 'plugin'},
                    'attr_2': {'value': 'test_2'}}
            },
            attributes
        )

    def test_update_plugin_node_attributes(self):
        self.env.create_plugin(
            name='plugin_b',
            cluster=self.cluster,
            enabled=True,
            package_version='5.0.0',
            node_attributes_metadata={
                'section_plugin_b': {
                    'attr_b': {'value': 'test_b'}
                }
            })
        new_attrs = PluginManager.get_plugin_node_attributes(self.node)
        new_attrs['plugin_a_section_1']['attr_1']['value'] = 'new_test_1'
        new_attrs['section_plugin_b']['attr_b']['value'] = 'new_test_b'
        PluginManager.update_plugin_node_attributes(new_attrs)
        attributes = PluginManager.get_plugin_node_attributes(self.node)
        for attribute in attributes:
            del attributes[attribute]['metadata']['node_plugin_id']
        self.assertDictEqual(
            {
                'plugin_a_section_1': {
                    'metadata': {'label': 'Section 1 of Plugin A',
                                 'class': 'plugin'},
                    'attr_1': {'value': 'new_test_1'}},
                'plugin_a_section_2': {
                    'metadata': {'class': 'plugin'},
                    'attr_2': {'value': 'test_2'}},
                'section_plugin_b': {
                    'metadata': {'class': 'plugin'},

                    'attr_b': {'value': 'new_test_b'}}
            },
            attributes
        )

    def test_add_plugin_attributes_for_node(self):
        new_cluster_node = self.env.create_node(
            cluster_id=self.cluster.id,
            roles=['controller']
        )
        PluginManager.add_plugin_attributes_for_node(new_cluster_node)
        node_cluster_plugins = new_cluster_node.node_cluster_plugins
        self.assertEqual(len(node_cluster_plugins), 1)
        attributes = node_cluster_plugins[0].attributes
        self.assertDictEqual(
            {
                'plugin_a_section_1': {
                    'metadata': {'label': 'Section 1 of Plugin A'},
                    'attr_1': {'value': 'test_1'}},
                'plugin_a_section_2': {
                    'attr_2': {'value': 'test_2'}}
            },
            attributes
        )


class TestNICIntegration(base.BaseTestCase):

    def setUp(self):
        super(TestNICIntegration, self).setUp()

        self.cluster = self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': '2015.1-8.0'})

        self.env.create_plugin(
            name='plugin_a',
            cluster=self.cluster,
            enabled=True,
            package_version='5.0.0',
            nic_attributes_metadata={'attr_a': {'value': 'test_a'}})
        self.node = self.env.create_nodes_w_interfaces_count(
            1, 1, **{"cluster_id": self.cluster.id})[0]
        self.interface = self.node.nic_interfaces[0]

    def test_get_nic_default_attributes(self):
        self.env.create_plugin(
            name='plugin_b',
            cluster=self.cluster,
            enabled=True,
            package_version='5.0.0',
            nic_attributes_metadata={'attr_b': {'value': 'test_b'}})
        default_attributes = PluginManager.get_nic_default_attributes(
            self.cluster)
        self.assertDictEqual({
            'plugin_a': {
                'metadata': {'label': 'Test plugin', 'class': 'plugin'},
                'attr_a': {'value': 'test_a'}},
            'plugin_b': {
                'metadata': {'label': 'Test plugin', 'class': 'plugin'},
                'attr_b': {'value': 'test_b'}}
        }, default_attributes)

    def test_get_nic_plugin_atributes(self):
        attributes = PluginManager.get_nic_attributes(self.interface)
        del attributes['plugin_a']['metadata']['nic_plugin_id']
        self.assertDictEqual(
            {'plugin_a': {
                'attr_a': {'value': 'test_a'},
                'metadata': {
                    'class': 'plugin',
                    'label': 'Test plugin'}}}, attributes)

    def test_update_nic_attributes(self):
        new_attrs = PluginManager.get_nic_attributes(self.interface)
        new_attrs['plugin_a']['attr_a']['value'] = {}
        PluginManager.update_nic_attributes(new_attrs)
        attributes = PluginManager.get_nic_attributes(self.interface)
        del attributes['plugin_a']['metadata']['nic_plugin_id']
        self.assertDictEqual(
            {'plugin_a': {
                'attr_a': {'value': {}},
                'metadata': {
                    'class': 'plugin',
                    'label': 'Test plugin'}}}, attributes)
