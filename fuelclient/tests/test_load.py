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
import os
import sys
import unittest2

import mock
import requests
from requests import models as req_models
from six import moves as six_moves

from fuelclient import client
from fuelclient import consts
from fuelclient.objects import node
from fuelclient.cli import parser
from fuelclient import profiler
from tests import base
from tests import utils


@unittest2.skipUnless(profiler.profiling_enabled(), 'Enviroment variable %s '
                      'is not set.' % consts.PERF_TEST_VAR)
@mock.patch.object(client.Client, 'auth_token', new_callable=mock.MagicMock)
@mock.patch.object(requests.api, 'request')
class ClientLoadTest(base.BaseTestCase):

    NUMBER_OF_NODES = 100

    @classmethod
    def setUpClass(cls):
        super(ClientLoadTest, cls).setUpClass()
        cls.nodes = cls.get_random_nodes(cls.NUMBER_OF_NODES)

    @classmethod
    def get_random_nodes(cls, number):
        """Returns specified number of random fake nodes."""

        return [utils.get_fake_node() for i in six_moves.range(number)]

    def invoke_client(self, *args):
        """Invokes Fuel Client with the specified arguments."""

        p = parser.Parser()

        p.args = ['fuelclient'] + list(args)
        p.parse()

    def configure_mocks(self, m_request, *responses):
        """Mocks network requests in order to return specified content"""

        m_responces = []

        for resp in responses:
            m_resp = req_models.Response()
            m_resp.encoding = 'utf8'
            m_resp._content = resp

            m_responces.append(m_resp)

        m_request.side_effect = m_responces

    def test_list_nodes(self, m_request, m_auth):
        nodes_text = json.dumps(self.nodes)
        self.configure_mocks(m_request, nodes_text)

        self.invoke_client('node', 'list')


    def test_assign_nodes(self, m_request, m_auth):
        node_ids = ','.join([str(n['id']) for n in self.nodes])

        self.configure_mocks(m_request, '{}')
        self.invoke_client('--env', '42', 'node', 'set', '--node',
                           node_ids, '--role', 'compute')

    def test_list_environment(self, m_request, m_auth):
        # NOTE(romcheg): After 100 nodes were added to an environment
        # they are listed as pending changes so that may potentially
        # affect the performance.
        env = [utils.get_fake_env(changes_number=self.NUMBER_OF_NODES)]
        resp_text = json.dumps(env)

        self.configure_mocks(m_request,resp_text)

        self.invoke_client('env', '--list')

    @mock.patch.object(node, 'exit_with_error', new_callable=mock.MagicMock)
    @mock.patch('__builtin__.open', create=True)
    def test_upload_node_settings(self, m_open, m_exit, m_request, m_auth):
        node_configs = [json.dumps(utils.get_fake_network_config(3))
                        for i in six_moves.range(self.NUMBER_OF_NODES)]

        node_ids = ','.join([str(n['id']) for n in self.nodes])

        m_open.return_value = mock.MagicMock(spec=file)
        m_file = m_open.return_value.__enter__.return_value
        m_file.read.side_effect = node_configs

        self.configure_mocks(m_request, *node_configs)


        self.invoke_client('--json',  'node', '--node-id', node_ids,
                           '--network', '--upload', '--dir', '/fake/dir')
