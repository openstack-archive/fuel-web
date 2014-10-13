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
import os
import sys
import unittest2

import mock
import requests
from requests import models as req_models

from fuelclient import client
from fuelclient.cli import parser
from tests import base
from tests import utils


@unittest2.skipUnless(os.environ.get('NAILGUN_LOAD_TEST'),
                      "Enviroment variable NAILGUN_LOAD_TEST is not set.")
@mock.patch.object(client.Client, 'auth_token', new_callable=mock.MagicMock)
@mock.patch.object(requests.api, 'request')
@mock.patch.object(req_models.Response, 'text', new_callable=mock.PropertyMock)
class ClientLoadTest(base.BaseTestCase):

    def setUp(self):
        super(ClientLoadTest, self).setUp()

        self.node_number = int(os.environ.get('NAILGUN_LOAD_TEST_POWER', 100))
        self.nodes = self.get_random_nodes(self.node_number)

    def get_random_nodes(self, number):
        """Returns specified number of random fake nodes."""

        return [utils.get_fake_node() for i in xrange(number)]

    def invoke_client(self, *args):
        """Invokes Fuel Client with the specified arguments."""

        p = parser.Parser()

        p.args = ['fuelclient'] + list(args)
        p.parse()

    def configure_mocks(self, mock_request, mock_content, *responses):
        """Mocks network requests in order to return specified content"""

        mock_content.side_effect = responses
        fake_response = req_models.Response()
        fake_response.encoding = 'utf8'
        mock_request.return_value = fake_response

    def test_list_nodes(self, mock_text, mock_request, mock_auth_token):
        nodes_text = json.dumps(self.nodes)
        self.configure_mocks(mock_request, mock_text, nodes_text)

        self.invoke_client('node', 'list')


    def test_assign_nodes(self, mock_text, mock_request, mock_auth_token):
        node_ids = ','.join([str(n['id']) for n in self.nodes])

        self.configure_mocks(mock_request, mock_text, '{}')
        self.invoke_client('--env', '42', 'node', 'set', '--node',
                           node_ids, '--role', 'compute')

    def test_list_environment(self, mock_text, mock_request, mock_auth_token):
        # NOTE(romcheg): After 100 nodes were added to an environment
        # they are listed as pending changes so that may potentially
        # affect the performance.
        env = [utils.get_fake_env(changes_number=self.node_number)]
        resp_text = json.dumps(env)

        self.configure_mocks(mock_request, mock_text, resp_text)

        self.invoke_client('env', '--list')
