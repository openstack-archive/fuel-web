# -*- coding: utf-8 -*-
#
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

import json
import unittest

import mock
import requests
from six import moves as six_moves

from fuelclient.cli import parser
from fuelclient import client
from fuelclient.objects import node
from fuelclient import profiler
from fuelclient.tests import base
from fuelclient.tests import utils


class ClientPerfTest(base.BaseTestCase):

    NUMBER_OF_NODES = 100

    @classmethod
    def setUpClass(cls):
        super(ClientPerfTest, cls).setUpClass()

        if not profiler.profiling_enabled():
            raise unittest.SkipTest('Performance profiling tests are not '
                                    'enabled in settings.yaml')

        cls.nodes = cls.get_random_nodes(cls.NUMBER_OF_NODES)

    def setUp(self):
        super(ClientPerfTest, self).setUp()

        req_patcher = mock.patch.object(requests.api, 'request')
        token_patcher = mock.patch.object(client.Client, 'auth_token',
                                          new_callable=mock.PropertyMock)

        self.mock_request = req_patcher.start()
        self.mock_auth_token = token_patcher.start()

    def tearDown(self):
        super(ClientPerfTest, self).tearDown()

        self.mock_request.stop()
        self.mock_auth_token.stop()

    @classmethod
    def get_random_nodes(cls, number):
        """Returns specified number of random fake nodes."""

        return [utils.get_fake_node() for i in six_moves.range(number)]

    def invoke_client(self, *args):
        """Invokes Fuel Client with the specified arguments."""

        args = ['fuelclient'] + list(args)

        p = parser.Parser(args)
        p.parse()

    def mock_nailgun_response(self, *responses):
        """Mocks network requests in order to return specified content."""

        m_responses = []

        for resp in responses:
            m_resp = requests.models.Response()
            m_resp.encoding = 'utf8'
            m_resp._content = resp

            m_responses.append(m_resp)

        self.mock_request.side_effect = m_responses

    def test_list_nodes(self):
        nodes_text = json.dumps(self.nodes)
        self.mock_nailgun_response(nodes_text)

        self.invoke_client('node', 'list')

    def test_assign_nodes(self):
        node_ids = ','.join([str(n['id']) for n in self.nodes])

        self.mock_nailgun_response('{}')
        self.invoke_client('--env', '42', 'node', 'set', '--node',
                           node_ids, '--role', 'compute')

    def test_list_environment(self):
        # NOTE(romcheg): After 100 nodes were added to an environment
        # they are listed as pending changes so that may potentially
        # affect the performance.
        env = [utils.get_fake_env(changes_number=self.NUMBER_OF_NODES)]
        resp_text = json.dumps(env)

        self.mock_nailgun_response(resp_text)

        self.invoke_client('env', '--list')

    @mock.patch.object(node, 'exit_with_error', new_callable=mock.MagicMock)
    @mock.patch('__builtin__.open', create=True)
    def test_upload_node_settings(self, m_open, m_exit):
        node_configs = [json.dumps(utils.get_fake_network_config(3))
                        for i in six_moves.range(self.NUMBER_OF_NODES)]

        node_ids = ','.join([str(n['id']) for n in self.nodes])

        m_open.return_value = mock.MagicMock(spec=file)
        m_file = m_open.return_value.__enter__.return_value
        m_file.read.side_effect = node_configs

        self.mock_nailgun_response(*node_configs)

        self.invoke_client('--json', 'node', '--node-id', node_ids,
                           '--network', '--upload', '--dir', '/fake/dir')
