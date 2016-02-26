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


class TestNodeAttributesValidatorCpuPinning(base.BaseTestCase):
    def setUp(self):
        attributes = {
            'cpu_pinning': {
                'dpdk': {'description': 'Number of CPUs for DPDK usage',
                         'label': 'DPDK CPU pinning',
                         'regex': {'error': 'Incorrect value',
                                   'source': '^\\d+$'},
                         'type': 'text',
                         'value': '0',
                         'weight': 20},
                'metadata': {'group': 'nfv',
                             'label': 'CPU pinning',
                             'weight': 10},
                'nova': {'description': 'Number of CPUs for Nova usage',
                         'label': 'Nova CPU pinning',
                         'regex': {'error': 'Incorrect value',
                                   'source': '^\\d+$'},
                         'type': 'text',
                         'value': '0',
                         'weight': 10}}
        }

        meta = {'cpu': {'total': 8}}
        self.node = mock.Mock(meta=meta, attributes=attributes)

    def tearDown(self):
        pass

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
