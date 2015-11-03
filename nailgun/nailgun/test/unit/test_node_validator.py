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

from nailgun.api.v1.validators.json_schema import node_schema
from nailgun.api.v1.validators import node
from nailgun.errors import errors

from nailgun.test import base


class TestNodeJsonSchemaValidation(base.BaseValidatorTest):

    validator = node.NodeValidator.validate_schema

    def serialize(self, data):
        """No need to serialize data when we want to simply test json schema

        """
        return data

    def test_invalid_oneOf_node_label_value_greater_than_100_chars(self):
        invalid = {"a": "a" * 110}
        self.assertRaisesInvalidOneOf(
            {"labels": invalid},
            "'{0}'".format(invalid['a']),
            "['labels']",
            node_schema.single_schema
        )

    def test_invalid_oneOf_node_label_integer_value(self):
        invalid = {"a": 1}
        self.assertRaisesInvalidOneOf(
            {"labels": invalid},
            invalid["a"],
            "['labels']",
            node_schema.single_schema
        )

    def test_additional_property_not_allowed_node_label_key(self):
        key = "a" * 110
        invalid = {key: "a"}

        self.assertRaisesAdditionalProperty(
            {"labels": invalid},
            key,
            node_schema.single_schema
        )

    def test_invalid_oneOf_label_empty_string_value(self):
        invalid = {'a': ''}
        self.assertRaisesInvalidOneOf(
            {'labels': invalid},
            invalid['a'],
            "['labels']",
            node_schema.single_schema
        )

    def test_node_label_validation_successfull(self):
        valid = [
            {'a': 'a'},
            {'a': None}
        ]

        for data in valid:
            self.assertNotRaises(
                errors.InvalidData,
                self.validator,
                data,
                node_schema.single_schema)
