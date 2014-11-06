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

from mock import patch

from fuelclient.tests import base


API_INPUT = {'config': 'nova_network'}
API_OUTPUT = 'config: nova_network\n'


@patch('fuelclient.client.requests')
@patch('fuelclient.cli.serializers.open', create=True)
@patch('fuelclient.cli.actions.base.os')
class TestReleaseNetworkActions(base.UnitTestCase):

    def test_release_network_download(self, mos, mopen, mrequests):
        mrequests.get().json.return_value = API_INPUT
        self.execute(['fuel', 'rel', '--rel', '1', '--network', '--download'])
        mopen().__enter__().write.assert_called_once_with(API_OUTPUT)

    def test_release_network_upload(self, mos, mopen, mrequests):
        mopen().__enter__().read.return_value = API_OUTPUT
        self.execute(['fuel', 'rel', '--rel', '1', '--network', '--upload'])
        self.assertEqual(mrequests.put.call_count, 1)
        call_args = mrequests.put.call_args_list[0]
        url = call_args[0][0]
        kwargs = call_args[1]
        self.assertIn('releases/1/networks', url)
        self.assertEqual(
            json.loads(kwargs['data']), API_INPUT)
