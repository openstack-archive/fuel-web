# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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

import inspect

from nailgun.errors import errors
from nailgun.expression import Expression
from nailgun.test.base import BaseTestCase


class TestExpressionParser(BaseTestCase):

    def test_expression_parser(self):
        cluster = self.env.create_cluster(api=False, mode='ha_compact')
        models = {
            'cluster': cluster,
            'settings': cluster.attributes.editable,
            'release': cluster.release
        }
        hypervisor = models['settings']['common']['libvirt_type']['value']

        test_cases = (
            # test scalars
            ('true', True),
            ('false', False),
            ('123', 123),
            ('"123"', '123'),
            ("'123'", '123'),
            # test null
            ('null', None),
            ('null == false', False),
            ('null == true', False),
            ('null == null', True),
            # test boolean operators
            ('true or false', True),
            ('true and false', False),
            ('not true', False),
            # test precedence
            ('true or true and false or false', True),
            ('true == true and false == false', True),
            # test comparison
            ('123 == 123', True),
            ('123 == 321', False),
            ('123 != 321', True),
            ('123 != "123"', True),
            # test grouping
            ('(true or true) and not (false or false)', True),
            # test errors
            ('(true', errors.ParseError),
            ('false and', errors.ParseError),
            ('== 123', errors.ParseError),
            ('#^@$*()#@!', errors.ParseError),
            # test modelpaths
            ('cluster:mode', 'ha_compact'),
            ('cluster:mode == "ha_compact"', True),
            ('cluster:mode != "multinode"', True),
            ('"controller" in release:roles', True),
            ('"unknown-role" in release:roles', False),
            ('settings:common.libvirt_type.value', hypervisor),
            ('settings:common.libvirt_type.value == "{0}"'.format(hypervisor),
                True),
            ('cluster:mode == "ha_compact" and not ('
                'settings:common.libvirt_type.value '
                '!= "{0}")'.format(hypervisor), True),
            # test nonexistent keys
            ('cluster:nonexistentkey', TypeError),
            # test evaluation flow
            ('cluster:mode != "ha_compact" and cluster:nonexistentkey == 1',
                False),
            ('cluster:mode == "ha_compact" and cluster:nonexistentkey == 1',
                TypeError),
        )

        def evaluate_expression(expression, models):
            return Expression(expression, models).evaluate()

        for test_case in test_cases:
            expression, result = test_case
            if inspect.isclass(result) and issubclass(result, Exception):
                self.assertRaises(result, evaluate_expression,
                                  expression, models)
            else:
                self.assertEqual(evaluate_expression(expression, models),
                                 result)
