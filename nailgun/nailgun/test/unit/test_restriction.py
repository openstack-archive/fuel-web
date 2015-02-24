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

import six
import yaml

from nailgun.errors import errors
from nailgun.objects.base import RestrictionMixin
from nailgun.test import base


class TestRestriction(base.BaseUnitTest):

    def setUp(self):
        super(TestRestriction, self).setUp()
        test_data = """
            attributes_1:
              group:
                test_attribute_1:
                  name: test_attribute_1
                  value: true
                  restrictions:
                    - condition: 'settings:group.test_attribute_2.value ==
                        true'
                      message: 'Only one of attributes 1 and 2 allowed'
                    - condition: 'settings:group.test_attribute_3.value ==
                        "spam"'
                      message: 'Only one of attributes 1 and 3 allowed'
                test_attribute_2:
                  name: test_attribute_2
                  value: true
                test_attribute_3:
                  name: test_attribute_3
                  value: spam
                  restrictions:
                    - condition: 'settings:group.test_attribute_3.value ==
                        settings:group.test_attribute_4.value'
                      message: 'Only one of attributes 3 and 4 allowed'
                      action: enable
                test_attribute_4:
                  name: test_attribute_4
                  value: spam
        """
        self.data = yaml.load(test_data)

    def tearDown(self):
        super(TestRestriction, self).tearDown()
        RestrictionMixin.expanded_restrictions = {}

    def test_check_restrictions(self):
        attributes = self.data.get('attributes_1')

        for gkey, gvalue in six.iteritems(attributes):
            for key, value in six.iteritems(gvalue):
                restrictions = []
                if 'restrictions' in value:
                    restrictions = map(
                        RestrictionMixin._expand_restriction,
                        value.get('restrictions'))
                result = RestrictionMixin.check_restrictions(
                    models={'settings': attributes},
                    restrictions=restrictions)
                # check when couple restrictions true for some item
                if key == 'test_attribute_1':
                    self.assertTrue(bool(result.get('result')))
                    self.assertEqual(
                        result.get('message'),
                        'Only one of attributes 1 and 2 allowed;' +
                        'Only one of attributes 1 and 3 allowed')
                # check when different values uses in restriction
                if key == 'test_attribute_3':
                    self.assertTrue(bool(result.get('result')))
                    self.assertEqual(
                        result.get('message'),
                        'Only one of attributes 3 and 4 allowed')

    def test_expand_restriction_format(self):
        string_restriction = 'settings.some_attribute.value != true'
        dict_restriction_long_format = {
            'condition': 'settings.some_attribute.value != true',
            'message': 'Another attribute required'
        }
        dict_restriction_short_format = {
            'settings.some_attribute.value != true':
            'Another attribute required'
        }
        result = {
            'action': 'disable',
            'condition': 'settings.some_attribute.value != true',
        }
        invalid_format = ['some_condition']

        # check string format
        self.assertDictEqual(
            RestrictionMixin._expand_restriction(
                string_restriction), result)
        result['message'] = 'Another attribute required'
        # check long format
        self.assertDictEqual(
            RestrictionMixin._expand_restriction(
                dict_restriction_long_format), result)
        # check short format
        self.assertDictEqual(
            RestrictionMixin._expand_restriction(
                dict_restriction_short_format), result)
        # check invalid format
        self.assertRaises(
            errors.InvalidData,
            RestrictionMixin._expand_restriction,
            invalid_format)
