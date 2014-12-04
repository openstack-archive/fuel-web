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

from mock import call
from mock import patch
from nailgun.api.v1.handlers.master_node_settings import \
    MasterNodeSettingsHandler
from nailgun.test.base import BaseUnitTest


@patch('web.webapi.ctx')
class TestMasterNodeSettingsHandler(BaseUnitTest):

    def setUp(self):
        super(TestMasterNodeSettingsHandler, self).setUp()
        self.handler = MasterNodeSettingsHandler()

    def tearDown(self):
        super(TestMasterNodeSettingsHandler, self).tearDown()
        del self.handler

    @patch.object(MasterNodeSettingsHandler, 'single')
    @patch.object(MasterNodeSettingsHandler, 'get_one_or_404')
    def test_get(self, mock_get_one_or_404, *args):
        self.handler.GET()
        self.handler.get_one_or_404.assert_called_once_with()
        self.handler.single.to_json.assert_called_once_with(
            mock_get_one_or_404())

    @patch.object(MasterNodeSettingsHandler, 'single')
    @patch.object(MasterNodeSettingsHandler, 'checked_data')
    @patch.object(MasterNodeSettingsHandler, 'validator')
    @patch.object(MasterNodeSettingsHandler, 'get_one_or_404')
    def test_put(self, mock_get_one_or_404,
                 mock_validator, mock_checked_data, *args):
        self.handler.PUT()
        self.handler.checked_data.assert_called_once_with(
            mock_validator.validate_update)
        self.handler.get_one_or_404.assert_called_once_with()

        self.assertEqual(self.handler.single.mock_calls, [
            call.update(mock_get_one_or_404(), mock_checked_data()),
            call.to_json(mock_get_one_or_404())
        ])
