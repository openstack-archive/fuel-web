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

from mock import patch
import unittest

from dhcp_checker import utils

IP_LINK_SHOW_UP = (
    "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>"
    "mtu 1500 qdisc pfifo_fast state UP qlen 1000"
    "link/ether 08:60:6e:6f:70:09 brd ff:ff:ff:ff:ff:ff"
)

IP_LINK_SHOW_DOES_NOT_EXIST = 'Device "eth2" does not exist.'


class TestDhcpUtils(unittest.TestCase):

    def test_command_utils_helper(self):
        command = utils.command_util('echo', 'hello')
        self.assertEqual(command.stdout.read(), 'hello\n')

    @patch('dhcp_checker.utils.command_util')
    def test_check_iface_state_up(self, command_util):
        command_util().stdout.read.return_value = IP_LINK_SHOW_UP
        self.assertEqual(utils._iface_state('eth0'), 'UP')

    @patch('dhcp_checker.utils.command_util')
    def test_check_network_up(self, command_util):
        command_util().stdout.read.return_value = IP_LINK_SHOW_UP
        self.assertTrue(utils.check_network_up('eth0'))

    @patch('dhcp_checker.utils.command_util')
    def test_check_iface_doesnot_exist(self, command_util):
        command_util().stderr.read.return_value = IP_LINK_SHOW_DOES_NOT_EXIST
        self.assertFalse(utils.check_iface_exist('eth2'))

    @patch('dhcp_checker.utils.command_util')
    def test_check_iface_exist(self, command_util):
        command_util().stderr.read.return_value = ''
        self.assertTrue(utils.check_iface_exist('eth0'))
