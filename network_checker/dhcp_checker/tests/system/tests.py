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
"""
For this tests you need
vagrant up develop dhcp1 dhcp2
"""

import unittest

from dhcp_checker import api
from dhcp_checker import utils


class TestDhcpServers(unittest.TestCase):

    def test_dhcp_server_on_eth1(self):
        """Test verifies dhcp server on eth1 iface"""
        response = api.check_dhcp_on_eth('eth1', 2)
        self.assertEqual(len(response), 1)
        # we need to guarantee that received answer has server_ip
        # but dont want to check its real address
        self.assertTrue(response[0]['server_ip'])

    def test_dhcp_server_on_eth2(self):
        """Test verifies dhcp server on eth2 iface"""
        response = api.check_dhcp_on_eth('eth2', 2)
        self.assertEqual(len(response), 1)
        self.assertTrue(response[0]['server_ip'])


class TestDhcpUtils(unittest.TestCase):

    def setUp(self):
        self.iface_down = 'eth1'
        utils.command_util('ifconfig', self.iface_down, 'down')

    def test_check_network_up(self):
        """Verify that true would be returned on test network up"""
        result = utils.check_network_up('eth0')
        self.assertTrue(result)

    def test_check_network_down(self):
        """Verify that false would be returned on test network down"""
        self.assertFalse(utils.check_network_up(self.iface_down))

    def tearDown(self):
        utils.command_util('ifconfig', self.iface_down, 'up')


class TestDhcpWithNetworkDown(unittest.TestCase):

    def setUp(self):
        self.iface_up = 'eth0'
        self.iface_down = 'eth2'
        utils.command_util('ifconfig', self.iface_down, 'down')

    def test_dhcp_server_on_eth2_down(self):
        """iface should be ifuped in case it's down and rolledback after"""
        manager = utils.IfaceState(self.iface_down)
        with manager as iface:
            response = api.check_dhcp_on_eth(iface, 2)

        self.assertEqual(len(response), 1)
        self.assertTrue(response[0]['server_ip'])
        self.assertEqual(manager.pre_iface_state, 'DOWN')
        self.assertEqual(manager.iface_state, 'UP')
        self.assertEqual(manager.post_iface_state, 'DOWN')

    def test_dhcp_server_on_eth0_up(self):
        """Test verifies that if iface is up, it won't be touched"""
        manager = utils.IfaceState(self.iface_up)
        with manager as iface:
            response = api.check_dhcp_on_eth(iface, 2)

        self.assertEqual(len(response), 1)
        self.assertTrue(response[0]['server_ip'])
        self.assertEqual(manager.pre_iface_state, 'UP')
        self.assertEqual(manager.iface_state, 'UP')
        self.assertEqual(manager.post_iface_state, 'UP')

    def test_dhcp_server_on_nonexistent_iface(self):

        def test_check():
            manager = utils.IfaceState('eth10')
            with manager as iface:
                api.check_dhcp_on_eth(iface, 2)
        self.assertRaises(EnvironmentError, test_check)

    def tearDown(self):
        utils.command_util('ifconfig', self.iface_down, 'up')


class TestMainFunctions(unittest.TestCase):

    def test_with_vlans(self):
        config = {'eth1': (103, 105),
                  'eth2': range(106, 120)}
        result = api.check_dhcp_with_vlans(config)
        self.assertEqual(len(list(result)), 2)

    def test_with_duplicated_with_repeat(self):
        ifaces = ['eth1', 'eth2']
        result = api.check_dhcp(ifaces, repeat=3)
        self.assertEqual(len(list(result)), 2)


if __name__ == '__main__':
    unittest.main()
