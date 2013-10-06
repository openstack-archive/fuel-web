# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from mock import patch

from nailgun.test import base


class TestVolumeManager(base.BaseIntegrationTest):

    def setUp(self):
        super(TestVolumeManager, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
            ]
        )
        self.node = self.env.nodes[0]
        self.volume_manager = self.node.volume_manager

    def assert_mounted_on(self, volumes, mount_point):
        volumes_types = (v['volumes'][0]['mount'] == mount_point
                         for v in volumes)
        self.assertTrue(volumes_types)

    def test_find_mounted_on_boot(self):
        mounted_volumes = list(self.volume_manager.
                               _find_mounted_on(key='/boot'))
        self.assertEqual(len(mounted_volumes), 6)
        self.assert_mounted_on(mounted_volumes, '/boot')

    def test_find_mounted_on_var_lib_glance(self):
        mounted_volumes = list(self.volume_manager.
                               _find_mounted_on(key='/var/lib/glance'))
        self.assert_mounted_on(mounted_volumes, '/var/lib/glance')

    def test_get_volume_size_helper(self):
        volumes = [
            {'volumes': [
                {'size': 10},
                {'size': 20}]},
            {'volumes': [
                {'size': 10},
                {'size': 20}]},
        ]
        expected = 60

        self.assertEqual(self.volume_manager._get_volumes_size(volumes),
                         expected)

    def test_glance_cache_size_property(self):
        volumes_size = 120 * 1024 * 1024 * 1024
        with patch.object(self.volume_manager,
                          '_get_volumes_size') as get_size:
            get_size.return_value = volumes_size
            result = self.volume_manager.glance_cache_size
        self.assertEqual(result, str(int(volumes_size * 0.1)))

    def test_glance_cache_size_property_less_then_5gb(self):
        volumes_size = 30 * 1024 * 1024 * 1024
        default = 5 * 1024 * 1024 * 1024
        with patch.object(self.volume_manager,
                          '_get_volumes_size') as get_size:
            get_size.return_value = volumes_size
            result = self.volume_manager.glance_cache_size
        self.assertEqual(result, str(default))
