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
from nailgun.volumes import manager


class TestVolumeManagerHelpers(base.BaseIntegrationTest):

    def setUp(self):
        super(TestVolumeManagerHelpers, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller']},
            ]
        )
        self.node = self.env.nodes[0]
        self.volumes = self.node.attributes.volumes

    def test_get_volumes_by_name(self):
        result = manager.get_logical_volumes_by_name(
            self.volumes, 'glance', 'image')
        self.assertEqual(len(list(result)), 1)

    def test_glance_cache_size_property_more_than_5gb(self):
        volumes_size = manager.gb_to_mb(120)
        with patch.object(manager,
                          'find_size_by_name') as get_size:
            get_size.return_value = volumes_size
            result = manager.calc_glance_cache_size(self.volumes)
        self.assertEqual(result,
                         str(int(manager.mb_to_byte(volumes_size) * 0.1)))

    def test_glance_cache_size_property_less_then_5gb(self):
        volumes_size = manager.gb_to_mb(30)
        default = manager.gb_to_byte(5)
        with patch.object(manager,
                          'find_size_by_name') as get_size:
            get_size.return_value = volumes_size
            result = manager.calc_glance_cache_size(self.volumes)
        self.assertEqual(result, str(default))
