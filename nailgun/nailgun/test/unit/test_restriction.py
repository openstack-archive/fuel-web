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
import yaml

import nailgun.objects
from nailgun.test import base


class TestRestriction(base.BaseUnitTest):

    def setUp(self):
        super(TestRestriction, self).setUp()
        test_data = """
            attributes:
                test_attributes_1:
                    name: test_restriction_1
                    value: true
                    restrictions:
                        - condition: attributes.test_attribute_2 == true
                          message: 'Only one of attributes allowed'
                test_attribute_2:
                    name: test_attribute_2
                    value: true
        """
        self.data = yaml.load(test_data)

    def test_check_restriction(self):
        pass

    def test_expand_restriction(self):
        pass

    def test_check_limits(self):
        pass

    def test_expand_limits(self):
        pass