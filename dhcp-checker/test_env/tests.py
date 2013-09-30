#!/usr/bin/python
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

import unittest

from dhcp_checker import api


class TestDhcpServers(unittest.TestCase):

    def test_dhcp_server_on_eth0(self):
        response = api.check_dhcp_on_eth('eth0', 5)
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0]['server_ip'], '10.0.2.2')

    def test_dhcp_server_on_eth1(self):
        response = api.check_dhcp_on_eth('eth1', 5)
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0]['server_ip'], '192.168.0.5')

    def test_dhcp_server_on_eth2(self):
        response = api.check_dhcp_on_eth('eth2', 5)
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0]['server_ip'], '10.10.0.10')
