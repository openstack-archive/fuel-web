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

import os
import unittest

from mock import patch
from scapy import all as scapy

from dhcp_checker import api

dhcp_options = [("message-type", "offer"), "end"]

request = (
    scapy.Ether(),
    scapy.Ether(src="", dst="ff:ff:ff:ff:ff:ff") /
    scapy.IP(src="0.0.0.0", dst="255.255.255.255") /
    scapy.UDP(sport=68, dport=67) /
    scapy.BOOTP(chaddr="") /
    scapy.DHCP(options=dhcp_options)
)

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


class TestDhcpApi(unittest.TestCase):

    def setUp(self):
        directory_path = os.path.dirname(__file__)
        self.scapy_data = list(scapy.rdpcap(os.path.join(directory_path,
                                                         'dhcp.pcap')))
        self.dhcp_response = self.scapy_data[1:]

    @patch('dhcp_checker.api.scapy.srp')
    @patch('dhcp_checker.api.scapy.get_if_raw_hwaddr')
    def test_check_dhcp_on_eth(self, raw_hwaddr, srp_mock):
        raw_hwaddr.return_value = ('111', '222')
        srp_mock.return_value = ([self.dhcp_response], [])
        response = api.check_dhcp_on_eth('eth1', timeout=5)
        self.assertEqual([expected_response], response)

    @patch('dhcp_checker.api.scapy.srp')
    @patch('dhcp_checker.api.scapy.get_if_raw_hwaddr')
    def test_check_dhcp_on_eth_empty_response(self, raw_hwaddr, srp_mock):
        raw_hwaddr.return_value = ('111', '222')
        srp_mock.return_value = ([], [])
        response = api.check_dhcp_on_eth('eth1', timeout=5)
        self.assertEqual([], response)

    @patch('dhcp_checker.api.send_dhcp_discover')
    @patch('dhcp_checker.api.make_listeners')
    def test_check_dhcp_with_multiple_ifaces(
            self, make_listeners, send_discover):
        api.check_dhcp(['eth1', 'eth2'])
        make_listeners.assert_called_once_with(('eth2', 'eth1'))
        self.assertEqual(send_discover.call_count, 2)

    @patch('dhcp_checker.api.send_dhcp_discover')
    @patch('dhcp_checker.api.make_listeners')
    def test_check_dhcp_with_vlans(self, make_listeners, send_discover):
        config_sample = {
            'eth0': (100, 101),
            'eth1': (100, 102)
        }
        api.check_dhcp_with_vlans(config_sample, timeout=1)
        make_listeners.assert_called_once_with(('eth1', 'eth0'))
        self.assertEqual(send_discover.call_count, 2)
