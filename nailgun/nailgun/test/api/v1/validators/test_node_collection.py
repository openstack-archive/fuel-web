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

from nailgun import consts

from nailgun.api.v1.validators.node import NodeCollectionValidator
from nailgun.errors import errors

from nailgun.test.base import BaseApiTest


class TestNodeCollectionValidator(BaseApiTest):

    DUMB_NODE = {
        'id': 1,
        'name': 'n',
        'status': consts.NODE_STATUSES.ready,
        'roles': [],
        'platform_name': None,
        'cluster_id': None,
        'ip': None,
        'error_type': None,
        'pending_addition': False,
        'fqdn': None,
        'kernel_params': None,
        'mac': None,
        'pending_deletion': True,
        'online': True,
        'progress': 100,
        'pending_roles': ['one', 'two'],
        'os_platform': 'op',
        'meta': {},
        'manufacturer': 'm',
        'network_data': []
    }

    def test_get_response(self):
        invalid_responses = [
            [{}],
            [{'id': 1}],
            [None],
            self.DUMB_NODE
        ]
        for response in invalid_responses:
            self.assertRaises(
                errors.InvalidData,
                NodeCollectionValidator.validate_get_response,
                response
            )

        valid_responses = [
            [],
            [self.DUMB_NODE],
            [self.DUMB_NODE, self.DUMB_NODE],
        ]
        for response in valid_responses:
            NodeCollectionValidator.validate_get_response(response)

    def test_post_request(self):
        invalid_requests = [
            {},
            {'mac': '60a44c3528ff'},
            {'mac': '60:a4:4c:35:28'},
            {'mac': None},
            {'xx': 'yy'}
        ]
        for request in invalid_requests:
            self.assertRaises(
                errors.InvalidData,
                NodeCollectionValidator.validate_post_request,
                request
            )

        valid_requests = [
            {'mac': '60:a4:4c:35:28:ff'},
            {'mac': '48-2C-6A-1E-59-3D'}
        ]
        for request in valid_requests:
            NodeCollectionValidator.validate_post_request(request)

    def test_post_response(self):
        invalid_responses = [
            {},
            {'id': 1},
            None,
        ]
        for response in invalid_responses:
            self.assertRaises(
                errors.InvalidData,
                NodeCollectionValidator.validate_post_response,
                response
            )

        valid_responses = [self.DUMB_NODE]
        for response in valid_responses:
            NodeCollectionValidator.validate_post_response(response)
