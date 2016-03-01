# coding: utf-8

# Copyright 2016 Mirantis, Inc.
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

import json
import mock
from nailgun.api.v1.validators import node as node_validator
from nailgun.errors import errors
from nailgun.test import base


validator = node_validator.NodeAttributesValidator.validate


class BaseNodeAttributeValidatorTest(base.BaseTestCase):
    def setUp(self):
        super(BaseNodeAttributeValidatorTest, self).setUp()

        meta = self.env.default_metadata()

        meta['numa_topology'] = {
            "supported_hugepages": [2048, 1048576],
            "numa_nodes": [
                {"id": 0, "cpus": [0, 1], 'memory': 2 * 1024 ** 3},
                {"id": 1, "cpus": [2, 3], 'memory': 2 * 1024 ** 3},
            ]
        }

        attributes = {
            'hugepages': {
                'nova': {
                    'type': 'custom_hugepages',
                    'value': {},
                },
                'dpdk': {
                    'type': 'text',
                    'value': '0',
                },
            },
            'cpu_pinning': {
                'dpdk': {
                    'type': 'text',
                    'value': '0',
                },
                'nova': {
                    'type': 'text',
                    'value': '0',
                }
            }
        }
        self.node = mock.Mock(meta=meta, attributes=attributes)


class TestNodeAttributesValidatorHugepages(BaseNodeAttributeValidatorTest):

    def test_defaults(self):
        data = {}

        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node)

    def test_valid_hugepages(self):
        data = {
            'hugepages': {
                'nova': {
                    'value': {
                        '2048': 1,
                        '1048576': 1,
                    },
                },
                'dpdk': {
                    'value': '2',
                },
            }
        }

        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node)

    def test_too_much_hugepages(self):
        data = {
            'hugepages': {
                'nova': {
                    'value': {
                        '2048': '100500',
                        '1048576': '100500',
                    },
                },
            },
        }

        self.assertRaisesWithMessageIn(
            errors.InvalidData, 'Too much memory allocated for huge pages',
            validator, json.dumps(data), self.node)

    def test_dpdk_requires_too_much(self):
        data = {
            'hugepages': {
                'dpdk': {
                    'value': '2049',
                },
            }
        }

        self.assertRaisesWithMessageIn(
            errors.InvalidData, 'requires more memory than numa node',
            validator, json.dumps(data), self.node)


class TestNodeAttributesValidatorCpuPinning(BaseNodeAttributeValidatorTest):
    def test_valid_data(self):
        data = {
            'cpu_pinning': {
                'nova': {'value': '1'},
            },
        }

        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node)

    def test_no_cpu_for_os(self):
        pinned_count = self.node.meta['cpu']['total']

        data = {
            'cpu_pinning': {
                'nova': {'value': str(pinned_count)},
            },
        }

        self.assertRaisesWithMessageIn(
            errors.InvalidData, 'at least one cpu',
            validator, json.dumps(data), self.node)

    def test_one_cpu_for_os(self):
        pinned_count = self.node.meta['cpu']['total'] - 1

        data = {
            'cpu_pinning': {
                'nova': {'value': str(pinned_count)},
            },
        }

        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node)
