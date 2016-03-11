# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

from mock import Mock
from mock import patch

from nailgun.errors import errors
from nailgun.test import base
from nailgun.utils.zabbix import ZabbixManager


class TestZabbixManager(base.BaseUnitTest):

    @patch('nailgun.utils.zabbix.urllib2.urlopen')
    def test_error_zabbix_request(self, mock_urlopen):
        urlopen_value = Mock()
        urlopen_value.read.return_value = json.dumps({
            'jsonrpc': '2.0',
            'id': '1',
            'error': {
                'message': "Error connecting to database]",
                'code': 1}})
        mock_urlopen.return_value = urlopen_value
        with self.assertRaises(errors.ZabbixRequestError):
            ZabbixManager._make_zabbix_request(
                'fake_url',
                'user.authenticate',
                {'password': 'zabbix', 'user': 'admin'},
                auth=None),
