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

from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema.base_types import NULLABLE_ID
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseApiTest


class TestHandler(BaseApiTest):
    def setUp(self):
        self.schema_module = self.SchemaImitator(
            GET_RESPONSE={
                'type': 'object',
                'properties': {
                    'id': NULLABLE_ID,
                },
                'required': ['id']
            },
            PUT_REQUEST={
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'name': {'type': 'string'}
                },
                'required': ['id']
            },
            PUT_RESPONSE={
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer'},
                    'name': {'type': 'string'}
                },
                'required': ['id', 'name']
            }
        )
        self.validator_patcher = mock.patch.object(
            BasicValidator,
            'schema_module',
            self.schema_module
        )
        self.addCleanup(self.validator_patcher.stop)
        self.validator_patcher.start()

    def _check_success(self, resp):
        self.assertNotIn('error_code', jsonutils.loads(resp))

    def _check_failure(self, resp):
        resp = jsonutils.loads(resp)
        self.assertIn('error_code', resp)
        self.assertEquals('InvalidData', resp['error_code'])

    def test_schema_module_is_loaded(self):
        self.assertIsNotNone(BasicValidator.schema_module)

    @mock.patch('web.header')
    @mock.patch('web.badrequest')
    @mock.patch('nailgun.api.v1.handlers.base.SingleHandler.single')
    @mock.patch('nailgun.api.v1.handlers.base.SingleHandler.get_object_or_404')
    def test_get_validation(self, _, __, ___, ____):
        handler = SingleHandler()

        # checking success response validation
        responses = [
            {'id': 3},
            {'id': None}
        ]
        for response in responses:
            with mock.patch.object(handler.single, 'to_dict',
                                   return_value=response):
                with mock.patch('web.data', return_value=jsonutils.dumps(3)):
                    resp = handler.GET(3)
                    self._check_success(resp)

        # checking error handling
        responses = [{'fake_field': 3}]
        for response in responses:
            with mock.patch.object(handler.single, 'to_dict',
                                   return_value=response):
                with mock.patch('web.data', return_value=jsonutils.dumps(3)):
                    resp = handler.GET(3)
                    self._check_failure(resp)

    @mock.patch('web.header')
    @mock.patch('web.badrequest')
    @mock.patch('nailgun.api.v1.handlers.base.SingleHandler.single')
    @mock.patch('nailgun.api.v1.handlers.base.SingleHandler.get_object_or_404')
    def test_put_validation(self, _, __, ___, ____):
        handler = SingleHandler()

        # checking success
        with mock.patch('web.data',
                        return_value=jsonutils.dumps({'id': 3, 'name': 'n'})):
            with mock.patch.object(handler.single, 'to_dict',
                                   return_value={'id': 3, 'name': 'n'}):
                resp = handler.PUT(3)
                self._check_success(resp)

        # checking request error handling
        with mock.patch('web.data', return_value=jsonutils.dumps({'idd': 3})):
            with mock.patch.object(handler.single, 'to_dict',
                                   return_value={'id': 3, 'name': 'n'}):
                resp = handler.PUT(3)
                self._check_failure(resp)

        # checking response error handling
        with mock.patch('web.data', return_value=jsonutils.dumps({'id': 3})):
            with mock.patch.object(handler.single, 'to_dict',
                                   return_value={'name': 'n'}):
                resp = handler.PUT(3)
                self._check_failure(resp)
