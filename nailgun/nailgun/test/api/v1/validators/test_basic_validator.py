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

import mock

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema.base_types import ID
from nailgun.api.v1.validators.json_schema.base_types import NET_ADDRESS
from nailgun.errors import errors
from nailgun.test.base import BaseApiTest


class TestBasicValidator(BaseApiTest):

    def test_success_on_empty_schema(self):
        BasicValidator.validate_schema({}, None)
        BasicValidator.validate_get_request(None)
        BasicValidator.validate_get_response(None)
        BasicValidator.validate_post_request(None)
        BasicValidator.validate_post_response(None)
        BasicValidator.validate_put_request(None)
        BasicValidator.validate_put_response(None)
        BasicValidator.validate_patch_request(None)
        BasicValidator.validate_patch_response(None)
        BasicValidator.validate_delete_request(None)
        BasicValidator.validate_delete_response(None)

    def test_get_request_schema(self):
        schema_module = TestBasicValidator.SchemaImitator(
            GET_REQUEST={
                'type': 'object',
                'properties': {
                    'cluster_id': ID,
                    'ip': NET_ADDRESS
                },
                'required': ['cluster_id']
            }
        )
        with mock.patch.object(BasicValidator, 'schema_module', schema_module):
            wrong_requests = [None, {'cluster_iddd': 3}, {'cluster_id': "22"},
                              {'cluster_id': None}, {'CLUSTER_ID': 3},
                              {'cluster_id': 3, 'ip': '1.2.3.4/300'}]
            for request in wrong_requests:
                self.assertRaises(
                    errors.InvalidData,
                    BasicValidator.validate_get_request,
                    request
                )
            right_requests = [{'cluster_id': 3}, {'cluster_id': 1, 'ip': '1.2.3.4/30'}]
            for request in right_requests:
                BasicValidator.validate_get_request(request)

    def test_get_response_schema(self):
        schema_module = self.SchemaImitator(
            GET_RESPONSE={
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'name': {'type': 'string'}
                },
                'required': ['id']
            }
        )
        with mock.patch.object(BasicValidator, 'schema_module', schema_module):
            wrong_requests = [None, {}, {'id': 3, 'name': 4}, {'name': "22"},
                              {'id': 4, 'name': None}]
            for request in wrong_requests:
                self.assertRaises(
                    errors.InvalidData,
                    BasicValidator.validate_get_response,
                    request
                )
            right_requests = [{'id': 3}, {'id': 3, 'name': "n"}]
            for request in right_requests:
                BasicValidator.validate_get_request(request)
