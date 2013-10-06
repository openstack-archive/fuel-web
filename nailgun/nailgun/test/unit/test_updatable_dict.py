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

import unittest

from nailgun.orchestrator.deployment_serializers import UpdatableDict


class TestUpdatableDict(unittest.TestCase):

    def test_nested_update(self):
        example_dict = UpdatableDict({
            'glance': {'password': 'something',
                       'username': 'else'}
        })
        example_dict.update_nested(
            {'glance': {'image_cache_max_size': '1000'}})
        expected = {'glance': {
            'password': 'something',
            'username': 'else',
            'image_cache_max_size': '1000'
        }}
        self.assertEqual(example_dict, expected)
