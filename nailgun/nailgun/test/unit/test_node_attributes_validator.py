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


class TestNodeAttributesValidatorHugepages(base.BaseTestCase):
    def setUp(self):
        super(TestNodeAttributesValidatorHugepages, self).setUp()
        meta = self.env.default_metadata()
        meta['numa_topology'] = {
            "supported_hugepages": [2048, 1048576],
            "numa_nodes": [
                {"id": 0, "cpus": [0, 1]},
                {"id": 1, "cpus": [2, 3]},
            ]
        }

        attributes = {
            'hugepages': {
                'metadata': {'group': 'nfv',
                             'label': 'Huge Pages',
                             'weight': 20},
                'nova': {'description': 'Nova Huge Pages',
                         'label': 'Nova Huge Pages',
                         'type': 'custom_hugepages',
                         'value': {},
                         'weight': 10}},
                'dpdk': {'description': 'DPDK',
                         'label': 'DPDK',
                         'regex': {'error': 'Incorrect value',
                                   'source': '^\\d+$'},
                         'type': 'text',
                         'value': '0',
                         'weight': 20},
        }
        self.node = mock.Mock(meta=meta, attributes=attributes)

    def test_defaults(self):
        data = {}

        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node)

    def test_valid_hugepages(self):
        data = {
            'hugepages': {
                'nova': {
                    'value': {
                        '2048': '1',
                        '1048576': '1',
                    },
                },
            },
            'dpdk': {
                'value': '1',
            },
        }

        self.assertNotRaises(errors.InvalidData, validator,
                             json.dumps(data), self.node)

    def test_to_much_hugepages(self):
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

        self.assertRaisesWithMessageIn(errors.InvalidData, 'huge pages',
                                       validator, json.dumps(data), self.node)
