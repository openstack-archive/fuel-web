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
class TestReleaseNetworkActions(base.UnitTestCase):

    def test_release_network_download(self, mrequests):
        self.execute(['fuel', 'rel', '--rel', '1', '--network', '--download'])
        mrequests.get.return_value = Mock(return_value={'config': 'nova_network'})
