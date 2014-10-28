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

from mock import Mock
from mock import patch

from fuelclient.tests import base

DATA = """
name: sample
version: 0.1.0
"""


@patch('fuelclient.client.requests')
class TestPluginsActions(base.UnitTestCase):

    def test_001_plugins_action(self, mrequests):
        self.execute(['fuel', 'plugins'])
        plugins_call = mrequests.get.call_args_list[-1]
        url = plugins_call[0][0]
        self.assertIn('api/v1/plugins', url)

    @patch('fuelclient.objects.plugins.tarfile')
    @patch('fuelclient.objects.plugins.os')
    def test_install_plugin(self, mos, mtar, mrequests):
        mos.path.exists.return_value = True
        mtar.open().getnames.return_value = ['metadata.yaml']
        mtar.open().extractfile().read.return_value = DATA
        response_mock = Mock(status_code=201)
        mrequests.post.return_value = response_mock
        self.execute(
            ['fuel', 'plugins', '--install', '/tmp/sample.fp'])
        self.assertEqual(mrequests.post.call_count, 1)
        self.assertEqual(mrequests.put.call_count, 0)

    @patch('fuelclient.objects.plugins.tarfile')
    @patch('fuelclient.objects.plugins.os')
    def test_install_plugin_with_force(self, mos, mtar, mrequests):
        mos.path.exists.return_value = True
        mtar.open().getnames.return_value = ['metadata.yaml']
        mtar.open().extractfile().read.return_value = DATA
        response_mock = Mock(status_code=409)
        response_mock.json.return_value = {'id': '12'}
        mrequests.post.return_value = response_mock
        self.execute(
            ['fuel', 'plugins', '--install', '/tmp/sample.fp', '--force'])
        self.assertEqual(mrequests.post.call_count, 1)
        self.assertEqual(mrequests.put.call_count, 1)
