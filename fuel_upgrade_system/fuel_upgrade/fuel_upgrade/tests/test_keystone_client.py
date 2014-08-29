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
import requests

from fuel_upgrade.clients import KeystoneClient
from fuel_upgrade.tests import base


class TestKeystoneClient(base.BaseTestCase):

    token = {'access': {'token': {'id': 'auth_token'}}}

    def setUp(self):
        self.credentials = {
            'username': 'some_user',
            'password': 'some_password',
            'auth_url': 'http://127.0.0.1:5000/v2',
            'tenant_name': 'some_tenant'}

        self.keystone = KeystoneClient(**self.credentials)

    @mock.patch('fuel_upgrade.clients.keystone_client.requests.post')
    @mock.patch('fuel_upgrade.clients.keystone_client.requests.Session')
    def test_makes_authenticated_requests(self, session, post_mock):
        post_mock.return_value.json.return_value = self.token
        self.keystone.request
        session.return_value.headers.update.assert_called_once_with(
            {'X-Auth-Token': 'auth_token'})

    @mock.patch('fuel_upgrade.clients.keystone_client.requests.Session')
    @mock.patch('fuel_upgrade.clients.keystone_client.requests.post',
                side_effect=requests.exceptions.HTTPError(''))
    def test_does_not_fail_without_keystone(self, _, __):
        self.keystone.request
        self.assertEqual(self.keystone.get_token(), None)
