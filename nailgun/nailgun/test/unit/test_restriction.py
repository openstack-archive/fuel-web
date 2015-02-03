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

from nailgun.objects.base import RestrictionMixin
from nailgun.test import base


class TestRestriction(base.BaseUnitTest):

    def setUp(self):
        super(TestRestriction, self).setUp()
        test_data = """
            attributes:
              test_attribute_1:
                name: test_restriction_1
                value: true
                action: enabled
                restrictions:
                  - condition: 'attributes:test_attribute_2.value == true'
                    message: 'Only one of attributes 1 and 2 allowed'
                  - condition: 'attributes:test_attribute_3.value == true'
                    message: 'Only one of attributes 1 and 3 allowed'
              test_attribute_2:
                name: test_attribute_2
                value: true
              test_attribute_3:
                name: test_attribute_3
                value: false
                restrictions:
                  - condition: 'attributes:test_attribute_4.value == true'
                    message: 'Only one of attributes 3 and 4 allowed'
              test_attribute_4:
                name: test_attribute_4
                value: false
        """
        self.data = yaml.load(test_data)

    def test_check_restriction(self):
        for key, value in six.iteritems(self.data.get('attributes', {})):
            if 'restrictions' in value:
                RestrictionMixin.expand_restriction(
                    value['restrictions'], '.'.join(['attributes', key]))

        for key in self.data.get('attributes', {}).keys():
            result = RestrictionMixin.check_restrictions(
                {'attributes': self.data.get('attributes')},
                'disabled',
                '.'.join(['attributes', key]))
            if result.get('result'):
                self.assertEqual(
                    result.get('message'),
                    'Only one of attributes 1 and 2 allowed')

    def test_expand_restriction(self):
        for key, value in six.iteritems(self.data.get('attributes', {})):
            if 'restrictions' in value:
                RestrictionMixin.expand_restriction(
                    value['restrictions'], '.'.join(['attributes', key]))

        test_expanded_restrictions = {
            'attributes.test_attribute_1': [
                {
                    'action': 'disabled',
                    'condition': 'attributes:test_attribute_2.value == true',
                    'message': 'Only one of attributes 1 and 2 allowed'
                },
                {
                    'action': 'disabled',
                    'condition': 'attributes:test_attribute_3.value == true',
                    'message': 'Only one of attributes 1 and 3 allowed'
                }
            ],
            'attributes.test_attribute_3': [
                {
                    'action': 'disabled',
                    'condition': 'attributes:test_attribute_4.value == true',
                    'message': 'Only one of attributes 3 and 4 allowed'
                }
            ]
        }
        self.assertEqual(
            test_expanded_restrictions,
            RestrictionMixin.expanded_restrictions)

    def test_check_limits(self):
        pass

    def test_expand_limits(self):
        pass
