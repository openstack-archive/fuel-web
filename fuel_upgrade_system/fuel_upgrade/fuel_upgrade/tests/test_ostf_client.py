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

from fuel_upgrade.clients import OSTFClient
from fuel_upgrade.tests import base


class TestOSTFClient(base.BaseTestCase):

    def setUp(self):
        mock_keystone = mock.MagicMock()
        self.mock_request = mock_keystone.request
        with mock.patch(
                'fuel_upgrade.clients.ostf_client.KeystoneClient',
                return_value=mock_keystone):
            self.ostf = OSTFClient('127.0.0.1', 8777)

    def test_get(self):
        self.ostf.get('/some_path')
        self.mock_request.get.assert_called_once_with(
            'http://127.0.0.1:8777/some_path')
