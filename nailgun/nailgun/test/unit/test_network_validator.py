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

import mock

from nailgun.api.v1.validators.network import NICsNamesValidator
from nailgun.errors import errors
from nailgun.test.base import BaseUnitTest


class TestNICsNamesValidator(BaseUnitTest):
    def setUp(self):
        self.valid_data = [
            [],
            [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
            [{"id": 1, "name": "a", "extra": "extra"}, {"id": 2, "name": "b"}]
        ]
        self.invalid_data = [
            None,
            {},
            [{}],
            [{"id": 1}],
            [{"id": 1, "name": "a"}, {"id": 2}],
            [{"id": 1, "name": "a"}, {"id": 1, "name": "b"}]
        ]

    @mock.patch.object(NICsNamesValidator, 'validate_json')
    def test_validate_nics_names_on_valid_data(self, validate_json_mock):
        for item in self.valid_data:
            validate_json_mock.return_value = item
            self.assertEqual(NICsNamesValidator.validate_nics_names(item),
                             item)

    @mock.patch.object(NICsNamesValidator, 'validate_json')
    def test_validate_nics_names_on_invalid_data(self, validate_json_mock):
        for item in self.invalid_data:
            validate_json_mock.return_value = item
            self.assertRaises(errors.InvalidData,
                              NICsNamesValidator.validate_nics_names,
                              item)
