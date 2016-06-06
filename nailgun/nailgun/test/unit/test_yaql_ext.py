# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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
from oslo_serialization import jsonutils
import six
import yaml
import yaql
from yaql.language import exceptions

from nailgun.extensions import BaseExtension
from nailgun.test.base import BaseUnitTest
from nailgun import yaql_ext


class TestYaqlExt(BaseUnitTest):
    @classmethod
    def setUpClass(cls):
        cls.variables = {
            '$%new': {
                'nodes': [
                    {'uid': '1', 'role': 'compute'},
                    {'uid': '2', 'role': 'controller'}
                ],
                'configs': {
                    'nova': {
                        'value': 1,
                        'value2': None,
                    }
                },
                'cluster': {
                    'status': 'operational'
                },
            },
            '$%old': {
                'nodes': [
                    {'uid': '1', 'role': 'controller'},
                    {'uid': '2', 'role': 'compute'},
                ],
                'configs': {
                    'nova': {
                        'value': 2,
                        'value2': None
                    }
                },
                'cluster': {
                    'status': 'new'
                },
            }
        }
        cls.variables['$'] = cls.variables['$%new']

    def evaluate(self, expression, variables=None, engine=None):
        context = yaql_ext.create_context(
            add_datadiff=True, add_serializers=True
        )
        for k, v in six.iteritems(variables or self.variables):
            context[k] = v

        engine = engine or yaql_ext.create_engine()
        parsed_exp = engine(expression)
        return parsed_exp.evaluate(context=context)

    def test_new(self):
        result = self.evaluate(
            'new($.nodes.where($.role=compute))'
        )
        self.assertEqual([{'uid': '1', 'role': 'compute'}], result)

    def test_old(self):
        result = self.evaluate(
            'old($.nodes.where($.role=compute))'
        )
        self.assertEqual([{'uid': '2', 'role': 'compute'}], result)

    def test_added(self):
        self.assertEqual(
            [{'uid': '1', 'role': 'compute'}],
            self.evaluate('added($.nodes.where($.role=compute))')
        )

    def test_deleted(self):
        self.assertItemsEqual(
            [{'uid': '2', 'role': 'compute'}],
            self.evaluate('deleted($.nodes.where($.role=compute))')
        )

    def test_changed(self):
        self.assertTrue(self.evaluate('changed($.configs.nova.value)'))
        self.assertFalse(self.evaluate('changed($.configs.nova.value2)'))

    def test_added_if_no_old(self):
        variables = self.variables.copy()
        variables['$%old'] = {}
        self.assertItemsEqual(
            [{'uid': '1', 'role': 'compute'}],
            self.evaluate('added($.nodes.where($.role=compute))', variables)
        )

    def test_delete_if_no_old(self):
        variables = self.variables.copy()
        variables['$%old'] = {}
        self.assertIsNone(
            self.evaluate('deleted($.nodes.where($.role=compute))', variables)
        )

    def test_changed_if_no_old(self):
        variables = self.variables.copy()
        variables['$%old'] = {}
        self.assertTrue(
            self.evaluate('changed($.configs.nova.value)', variables)
        )
        self.assertTrue(
            self.evaluate('changed($.configs.nova.value2)', variables)
        )

    def test_changed_many(self):
        expressions = '$.configs.nova.value, $.configs.nova.value2'
        self.assertTrue(self.evaluate('changedAny({0})'.format(expressions)))
        self.assertFalse(self.evaluate('changedAll({0})'.format(expressions)))

    def test_undefined(self):
        variables = self.variables.copy()
        variables['$%old'] = {}
        self.assertTrue(
            self.evaluate('old($.configs.nova.value).isUndef()', variables),
        )

    def test_to_yaml(self):
        expected = yaml.safe_dump(
            self.variables['$%new']['configs'], default_flow_style=False
        )
        actual = self.evaluate('$.configs.toYaml()')
        self.assertEqual(expected, actual)

    def test_to_json(self):
        expected = jsonutils.dumps(self.variables['$%new']['configs'])
        actual = self.evaluate('$.configs.toJson()')
        self.assertEqual(expected, actual)

    def test_limit_iterables(self):
        engine = yaql.YaqlFactory().create({
            'yaql.limitIterators': 1,
            'yaql.convertTuplesToLists': True,
            'yaql.convertSetsToLists': True
        })
        functions = ['added', 'deleted', 'changed']

        expressions = ['$.nodes', '$.configs.nova']
        for exp in expressions:
            for func in functions:
                with self.assertRaises(exceptions.CollectionTooLargeException):
                    self.evaluate('{0}({1})'.format(func, exp), engine=engine)

        expressions = ['$.configs.nova.value', '$.cluster.status']
        for exp in expressions:
            for func in functions:
                self.evaluate('{0}({1})'.format(func, exp), engine=engine)


class TestYaqlExtWithExtensions(BaseUnitTest):

    class YaqlUtils(BaseExtension):

        name = 'yaql_utils'
        version = '1.0.0'
        description = "A set of helper functions for YAQL"

        @classmethod
        def setup_yaql_context(cls, context):
            context.register_function(lambda n: bool(n % 2), name="is_odd")

    def evaluage(self, expression):
        with mock.patch('nailgun.extensions.manager.get_all_extensions',
                        return_value=[self.YaqlUtils()]):
            context = yaql_ext.create_context(add_extensions=True)
            engine = yaql_ext.create_engine()

        parsed_exp = engine(expression)
        return parsed_exp.evaluate(context=context)

    def test_function_from_extension(self):
        self.assertTrue(self.evaluage('is_odd(1)'))
        self.assertFalse(self.evaluage('is_odd(2)'))
