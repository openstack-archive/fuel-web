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

from nailgun.orchestrator.deployment_serializers import dict_merge
from nailgun.test.base import BaseIntegrationTest


class TestUtils(BaseIntegrationTest):
    def test_dict_merge(self):
        custom = {"coord": [10, 10],
                  "pass": "qwerty",
                  "dict": {"body": "solid",
                           "color": "black",
                           "dict": {"stuff": "hz"}}}
        common = {"parent": None,
                  # this dict will extend the original
                  "dict": {"transparency": 100,
                           # this dict will replace the original
                           "dict": {"another_stuff": "hz"}}}
        dict_merge(custom, common)
        self.assertEqual(custom, {"coord": [10, 10],
                                  "parent": None,
                                  "pass": "qwerty",
                                  "dict": {"body": "solid",
                                           "color": "black",
                                           "transparency": 100,
                                           "dict": {"another_stuff": "hz"}}})
