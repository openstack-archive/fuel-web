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

from mock import mock_open
from mock import patch
import os
import tempfile

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import dict_merge
from nailgun.utils import evaluate_expression
from nailgun.utils import expand_restriction
from nailgun.utils import extract_env_version
from nailgun.utils import get_fuel_release_versions


class TestUtils(BaseIntegrationTest):

    def test_dict_merge(self):
        custom = {"coord": [10, 10],
                  "pass": "qwerty",
                  "dict": {"body": "solid",
                           "color": "black",
                           "dict": {"stuff": "hz"}}}
        common = {"parent": None,
                  "dict": {"transparency": 100,
                           "dict": {"another_stuff": "hz"}}}
        result = dict_merge(custom, common)
        self.assertEqual(result, {"coord": [10, 10],
                                  "parent": None,
                                  "pass": "qwerty",
                                  "dict": {"body": "solid",
                                           "color": "black",
                                           "transparency": 100,
                                           "dict": {"stuff": "hz",
                                                    "another_stuff": "hz"}}})

    def test_extract_env_version(self):
        # format: input, output pairs
        test_cases = [
            ('2014.1', '5.0'),
            ('2014.1-5.0', '5.0'),
            ('2014.1.1-5.0.1', '5.0.1'),
            ('2014.1.1-5.0.1-X', '5.0.1'),
            ('2014.1.1-5.1', '5.1'),
        ]

        for input_, output in test_cases:
            self.assertEqual(extract_env_version(input_), output)

    @patch('nailgun.utils.glob.glob', return_value=['test.yaml'])
    @patch('__builtin__.open', mock_open(read_data='test_data'))
    def test_get_release_versions(self, _):
        versions = get_fuel_release_versions(None)
        self.assertDictEqual({'test': 'test_data'}, versions)

    def test_get_release_versions_empty_file(self):
        with tempfile.NamedTemporaryFile() as tf:
            versions = get_fuel_release_versions(tf.name)
            self.assertDictEqual({os.path.basename(tf.name): None}, versions)

    def test_get_release_no_file(self):
        with tempfile.NamedTemporaryFile() as tf:
            file_path = tf.name
        self.assertFalse(os.path.exists(file_path))
        versions = get_fuel_release_versions(file_path)
        self.assertDictEqual({}, versions)

    def test_expand_restriction(self):
        string_restriction = 'settings.some_attribute != true'
        dict_restriction_long_form = {
            'condition': 'settings.some_attribute != true',
            'message': 'Another attribute required'
        }
        dict_restriction_short_form = {
            'settings.some_attribute != true': 'Another attribute required'
        }
        result = {
            'action': 'disabled',
            'condition': 'settings.some_attribute != true',
        }
        invalid_fromat = ['some_condition']

        self.assertEqual(
          expand_restriction(string_restriction), result)
        result['message'] = 'Another attribute required'
        self.assertEqual(
          expand_restriction(dict_restriction_long_form), result)
        self.assertEqual(
          expand_restriction(dict_restriction_short_form), result)
        self.assertRaises(
          Exception, expand_restriction, invalid_fromat)

    def test_evaluate_expression(self):
        settings = {
          'some_attribute': {
              'value': True
          }
        }
        models = {
            'settings': settings
        }

        test_expression = 'settings:some_attribute.value == true'
        self.assertTrue(evaluate_expression(test_expression, models))
        settings['some_attribute']['value'] = False
        self.assertFalse(evaluate_expression(test_expression, models))
