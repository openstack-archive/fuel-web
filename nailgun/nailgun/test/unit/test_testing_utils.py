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
import copy

from nailgun.test import base


class TestDataDiff(base.BaseUnitTest):
    def setUp(self):
        super(TestDataDiff, self).setUp()

        self.dict_a = {
            'a': '1',
            'b': {
                'c': 'string',
                'd': {
                    'e': (1, 2, 3),
                    'f': [4, 5, 6],
                },
            },
        }
        self.dict_b = copy.deepcopy(self.dict_a)

    def test_compare_dict(self):
        self.datadiff(self.dict_a, self.dict_b)

    def test_compare_different_values(self):
        self.dict_b['b']['c'] = 'different-string'
        with self.assertRaisesRegexp(AssertionError, 'Values differ'):
            self.datadiff(self.dict_a, self.dict_b)

    def test_compare_different_key_number(self):
        self.dict_b['g'] = 'extra-key'
        with self.assertRaisesRegexp(AssertionError,
                                     'Dicts have different keys number'):
            self.datadiff(self.dict_a, self.dict_b)

    def test_compare_different_same_key_number(self):
        del self.dict_b['a']
        self.dict_b['g'] = 'extra-key'
        with self.assertRaisesRegexp(AssertionError, 'Keys differ'):
            self.datadiff(self.dict_a, self.dict_b)

    def test_compare_different_dicts_with_ignore(self):
        self.dict_b['b']['c'] = 'different-string'
        self.datadiff(self.dict_a, self.dict_b, ignore_keys=('c', ))

    def test_compare_lists_with_different_order(self):
        self.dict_b['b']['d']['e'] = self.dict_b['b']['d']['e'][::-1]
        self.dict_b['b']['d']['f'] = self.dict_b['b']['d']['f'][::-1]
        with self.assertRaisesRegexp(AssertionError, 'Values differ'):
            self.datadiff(self.dict_a, self.dict_b)

    def test_compare_sorted_lists(self):
        self.dict_b['b']['d']['e'] = self.dict_b['b']['d']['e'][::-1]
        self.dict_b['b']['d']['f'] = self.dict_b['b']['d']['f'][::-1]
        self.datadiff(self.dict_a, self.dict_b, compare_sorted=True)
