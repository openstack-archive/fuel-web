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
from nailgun import consts
from nailgun.api.v1.validators import node as node_validator
from nailgun.errors import errors
from nailgun.test import base


validator = node_validator.NodeAttributesValidator.validate


class TestNodeAttributesValidator(base.BaseTestCase):
    def setUp(self):
        super(TestNodeAttributesValidator, self).setUp()
        self.env.create(
            api=False,
            release_kwargs={'operating_system': consts.RELEASE_OS.ubuntu},
            nodes_kwargs=[
                {'roles': ['compute']}])

        self.node = self.env.nodes[0]

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
