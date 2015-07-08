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
                'volumes': [{'id': name, 'type': 'vg'}],
                'volumes_roles_mapping': {
                    name: [{'allocate_size': 'min', 'id': name}]
                }
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
            'volumes': [
                {'id': 'test_plugin_1', 'type': 'vg'},
                {'id': 'test_plugin_2', 'type': 'vg'}
            ],
            'volumes_roles_mapping': {
                'test_plugin_1': [
                    {'allocate_size': 'min', 'id': 'test_plugin_1'}
                ],
                'test_plugin_2': [
                    {'allocate_size': 'min', 'id': 'test_plugin_2'}
                ],
            }
        }

        self.assertEqual(
            volumes_metadata, expected_volumes_metadata)

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
            'volumes': [], 'volumes_roles_mapping': {}}

        self.assertEqual(
            volumes_metadata, expected_volumes_metadata)

    @mock.patch.object(PluginAdapterV3, 'sync_metadata_to_db')
    def test_sync_metadata_for_all_plugins(self, sync_mock):
        PluginManager.sync_plugins_metadata()
        self.assertEqual(sync_mock.call_count, 2)

    @mock.patch.object(PluginAdapterV3, 'sync_metadata_to_db')
    def test_sync_metadata_for_specific_plugin(self, sync_mock):
        PluginManager.sync_plugins_metadata([self.env.plugins[0].id])
        self.assertEqual(sync_mock.call_count, 1)
