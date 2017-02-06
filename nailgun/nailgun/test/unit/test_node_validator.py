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

import re

from nailgun.api.v1.validators.json_schema import node_schema
from nailgun.api.v1.validators import node
from nailgun import errors

from nailgun.test import base
import unittest


class TestNodeJsonSchemaValidation(base.BaseValidatorTest):

    validator = node.NodeValidator.validate_schema

    def serialize(self, data):
        """No need to serialize data when we want to simply test json schema

        """
        return data

    def test_invalid_oneOf_node_label_value_greater_than_100_chars(self):
        invalid = {"a": "a" * 101}
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

    @unittest.skip('Figure how to fix json schema lib changes')
    def test_additional_property_not_allowed_node_label_key(self):
        key = "a" * 101
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
            {'a': 'a' * 100},
            {'a': None}
        ]

        for data in valid:
            self.assertNotRaises(
                errors.InvalidData,
                self.validator,
                data,
                node_schema.single_schema)

    def test_cpu_pinning(self):
        data = {
            'meta': {
                'numa_topology': {
                    'supported_hugepages': [2048, 1048576],
                    'numa_nodes': [
                        {'id': 1, 'cpus': [0, 1, 2, 3], 'memory': 1024},
                        {'id': 2, 'cpus': [4, 5, 6, 7], 'memory': 1024},
                    ],
                    'distances': [
                        ['1.0', '2.1'],
                        ['2.1', '1.0'],
                    ]
                },
            }
        }

        self.assertNotRaises(
            errors.InvalidData,
            self.validator,
            data,
            node_schema.single_schema
        )

    def test_cpu_pinning_fail(self):
        tests_data = [
            {
                'data': {
                    'meta': {
                        'numa_topology': {},
                        'distances': []}},
                'message': "'supported_hugepages' is a required property"
            },
            {
                'data': {
                    'meta': {
                        'numa_topology': {
                            'numa_nodes': [],
                            'supported_hugepages': [],
                            'distances': []}}},
                'message': "[] is too short"
            },
            {
                'data': {
                    'meta': {
                        'numa_topology': {
                            'numa_nodes': [
                                {'id': 0, 'cpus': [0, 1, 2, 3]},
                            ],
                            'supported_hugepages': [],
                            'distances': []}}},
                'message': "'memory' is a required property"
            }
        ]

        for test in tests_data:
            self.assertRaisesWithMessageIn(
                errors.InvalidData,
                test['message'],
                self.validator,
                test['data'],
                node_schema.single_schema
            )


class TestNodeVmsValidation(base.BaseUnitTest):

    def assertValidData(self, data):
        self.assertNotRaises(
            errors.InvalidData,
            node.NodeVMsValidator.validate_schema,
            data,
            node_schema.NODE_VM_SCHEMA
        )

    def assertInvalidData(self, data, regexp):
        self.assertRaisesRegexp(
            errors.InvalidData,
            regexp,
            node.NodeVMsValidator.validate_schema,
            data,
            node_schema.NODE_VM_SCHEMA
        )

    def test_schema_success(self):
        data = {'vms_conf': [{'id': 1, 'cpu': 2, 'mem': 4}]}
        self.assertValidData(data)

        data = {'vms_conf': [
            {'id': 1, 'vda_size': '100500'},
            {'id': 2, 'vda_size': '42G'},
        ]}
        self.assertValidData(data)

    def test_schema_fail_invalid_type(self):
        data = {'vms_conf': [[{}]]}
        self.assertInvalidData(data, r"\[{}\] is not of type 'object'")

    def test_schema_fail_invalid_value(self):
        data = {'vms_conf': [{'id': 1, 'cpu': -2}]}
        self.assertInvalidData(data, '-2 is less than the minimum of 1')
        data = {'vms_conf': [{'id': 1, 'mem': -4}]}
        self.assertInvalidData(data, '-4 is less than the minimum of 1')
        data = {'vms_conf': [{'id': 1, 'vda_size': '-4G'}]}
        self.assertInvalidData(data, r"'-4G' does not match '{0}'".format(
            re.escape(node_schema._VDA_SIZE_RE)))
        data = {'vms_conf': [{'id': 1, 'vda_size': 'G'}]}
        self.assertInvalidData(data, r"'G' does not match '{0}".format(
            re.escape(node_schema._VDA_SIZE_RE)))

    def test_schema_fail_missing_value(self):
        data = {'vms_conf': [{'cpu': 1, 'mem': 4}]}
        self.assertInvalidData(data, "'id' is a required property")
