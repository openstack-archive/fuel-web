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

from mock import Mock
from mock import mock_open
from mock import patch
import os
import tempfile

from nailgun.test import base
from nailgun.utils import camel_to_snake_case
from nailgun.utils import dict_merge
from nailgun.utils import extract_env_version
from nailgun.utils import get_fuel_release_versions
from nailgun.utils import traverse


class TestUtils(base.BaseUnitTest):

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

    def test_camel_case_to_snake_case(self):
        self.assertTrue(
            camel_to_snake_case('TestCase') == 'test_case')
        self.assertTrue(
            camel_to_snake_case('TTestCase') == 't_test_case')


class TestTraverse(base.BaseUnitTest):

    class TestGenerator(object):
        @classmethod
        def test(cls, arg=None):
            return 'testvalue'

    data = {
        'foo': {
            'generator': 'test',
        },
        'bar': 'test {a} string',
        'baz': 42,
        'regex': {
            'source': 'test {a} string',
            'error': 'an {a} error'
        }
    }

    def test_wo_formatting_context(self):
        result = traverse(self.data, self.TestGenerator)

        self.assertEqual(result, {
            'foo': 'testvalue',
            'bar': 'test {a} string',
            'baz': 42,
            'regex': {
                'source': 'test {a} string',
                'error': 'an {a} error'
            }})

    def test_w_formatting_context(self):
        result = traverse(self.data, self.TestGenerator, {'a': 13})

        self.assertEqual(result, {
            'foo': 'testvalue',
            'bar': 'test 13 string',
            'baz': 42,
            'regex': {
                'source': 'test {a} string',
                'error': 'an {a} error'
            }})


class TestTraverseUtil(base.BaseUnitTest):
    attrs = {
        'param1': {'generator': 'generator1'},
        'nested': {
            'param2': {'generator': 'generator2',
                       'generator_arg': 'gen_arg2'}
        },
        'nested_list': [
            'a',
            {'param3': 'some_value'},
            {'param4': {'generator': 'generator4',
                        'generator_arg': 'gen_arg4'}},
            ['v', 'a', 'l', {'u': 'e',
                             'param5': {'generator': 'generator5',
                                        'generator_arg': 'gen_arg5'}}]
        ]
    }

    def test_parameter_is_unchanged(self):
        obj1 = Mock()
        obj2 = traverse(obj1, Mock)
        self.assertFalse(obj1 is obj2)

    def test_process_dict_only(self):
        obj1 = [1, 2, 3]
        obj2 = traverse(obj1, Mock)
        self.assertEqual(obj1, obj2)

    def test_generate_attributes(self):
        generator_class = Mock()
        generator_class.generator1 = Mock(return_value='generated_value1')
        generator_class.generator2 = Mock(return_value='generated_value2')
        generator_class.generator4 = Mock(return_value='generated_value4')
        generator_class.generator5 = Mock(return_value='generated_value5')

        attrs = traverse(self.attrs, generator_class)

        generator_class.generator1.assert_called_once_with(None)
        generator_class.generator2.assert_called_once_with('gen_arg2')
        generator_class.generator4.assert_caled_once_with('gen_arg4')
        generator_class.generator5.assert_caled_once_with('gen_arg5')
        expected = {
            'param1': 'generated_value1',
            'nested': {'param2': 'generated_value2'},
            'nested_list': [
                'a',
                {'param3': 'some_value'},
                {'param4': 'generated_value4'},
                ['v', 'a', 'l', {'u': 'e', 'param5': 'generated_value5'}]
            ]
        }
        self.assertEqual(attrs, expected)

    def test_non_existent_generator(self):
        class Generator(object):
            pass

        self.assertRaises(AttributeError, traverse, self.attrs, Generator)
