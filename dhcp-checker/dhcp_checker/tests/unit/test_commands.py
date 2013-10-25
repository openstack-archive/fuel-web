#    Copyright 2013 Mirantis, Inc.
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
import unittest

from dhcp_checker import cli

expected_response = {
    'dport': 67,
    'gateway': '172.18.194.2',
    'iface': 'eth1',
    'mac': '00:15:17:ee:0a:a8',
    'message': 'offer',
    'server_id': '172.18.208.44',
    'server_ip': '172.18.194.2',
    'yiaddr': '172.18.194.35'
}


@patch('dhcp_checker.commands.api')
class TestCommandsInterface(unittest.TestCase):

    def test_list_dhcp_servers(self, api):
        api.check_dhcp.return_value = iter([expected_response])
        command = cli.main(['discover', '--ifaces', 'eth0', 'eth1',
                            '--format', 'json'])
        self.assertEqual(command, 0)
        api.check_dhcp.assert_called_once_with(['eth0', 'eth1'],
                                               repeat=2, timeout=5)

    def test_list_dhcp_assignment(self, api):
        api.check_dhcp_request.return_value = iter([expected_response])
        command = cli.main(['request', 'eth1', '10.20.0.2',
                            '--range_start', '10.20.0.10',
                            '--range_end', '10.20.0.20'])
        self.assertEqual(command, 0)
        api.check_dhcp_request.assert_called_once_with(
            'eth1', '10.20.0.2', '10.20.0.10', '10.20.0.20', timeout=5
        )

    def test_list_dhcp_vlans_info(self, api):
        config_sample = {'eth1': ['100', '101'],
                         'eth2': range(103, 110)}
        api.check_dhcp_with_vlans.return_value = iter([expected_response])
        command = cli.main(['vlans', json.dumps(config_sample)])
        self.assertEqual(command, 0)
        api.check_dhcp_with_vlans.assert_called_once_with(
            config_sample, repeat=2, timeout=5)
