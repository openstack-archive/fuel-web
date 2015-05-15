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

import unittest

from mock import call
from mock import Mock
from mock import patch
import netifaces

from url_access_checker import cli


@patch('url_access_checker.network.execute')
@patch('url_access_checker.network.netifaces.gateways')
@patch('requests.get', Mock(status_code=200))
@patch('url_access_checker.network.check_up')
@patch('url_access_checker.network.check_exist')
@patch('url_access_checker.network.check_ifaddress_present')
class TestVerificationWithNetworkSetup(unittest.TestCase):

    def assert_by_items(self, expected_items, received_items):
        """In case of failure will show difference only for failed item."""
        for expected, executed in zip(expected_items, received_items):
            self.assertEqual(expected, executed)

    def test_verification_route(self, mifaddr, mexist, mup, mgat, mexecute):
        mexecute.return_value = (0, '', '')
        mup.return_value = True
        mexist.return_value = True
        mifaddr.return_value = False

        default_gw, default_iface = '172.18.0.1', 'eth2'
        mgat.return_value = {
            'default': {netifaces.AF_INET: (default_gw, default_iface)}}

        iface = 'eth1'
        addr = '10.10.0.2/24'
        gw = '10.10.0.1'

        cmd = ['with', 'setup', '-i', iface,
               '-a', addr, '-g', gw, 'test.url']

        cli.main(cmd)

        execute_stack = [
            call(['ip', 'a']),
            call(['ip', 'ro']),
            call(['ip', 'a', 'add', addr, 'dev', iface]),
            call(['ip', 'ro', 'change', 'default', 'via', gw, 'dev', iface]),
            call(['ip', 'a']),
            call(['ip', 'ro']),
            call(['ip', 'ro', 'change', 'default', 'via', default_gw,
                  'dev', default_iface]),
            call(['ip', 'a', 'del', addr, 'dev', iface]),
            call(['ip', 'a']),
            call(['ip', 'ro'])]

        self.assert_by_items(mexecute.call_args_list, execute_stack)

    def test_verification_vlan(self, mifaddr, mexist, mup, mgat, mexecute):
        mexecute.return_value = (0, '', '')
        mup.return_value = False
        mexist.return_value = False
        mifaddr.return_value = False

        default_gw, default_iface = '172.18.0.1', 'eth2'
        mgat.return_value = {
            'default': {netifaces.AF_INET: (default_gw, default_iface)}}

        iface = 'eth1'
        addr = '10.10.0.2/24'
        gw = '10.10.0.1'
        vlan = '101'
        tagged_iface = '{0}.{1}'.format(iface, vlan)

        cmd = ['with', 'setup', '-i', iface,
               '-a', addr, '-g', gw, '--vlan', vlan, 'test.url']

        cli.main(cmd)

        execute_stack = [
            call(['ip', 'a']),
            call(['ip', 'ro']),
            call(['ip', 'link', 'set', 'dev', iface, 'up']),
            call(['ip', 'link', 'add', 'link', 'eth1', 'name',
                  tagged_iface, 'type', 'vlan', 'id', vlan]),
            call(['ip', 'link', 'set', 'dev', tagged_iface, 'up']),
            call(['ip', 'a', 'add', addr, 'dev', tagged_iface]),
            call(['ip', 'ro', 'change', 'default',
                  'via', gw, 'dev', tagged_iface]),
            call(['ip', 'a']),
            call(['ip', 'ro']),
            call(['ip', 'ro', 'change', 'default', 'via',
                  default_gw, 'dev', default_iface]),
            call(['ip', 'a', 'del', addr, 'dev', tagged_iface]),
            call(['ip', 'link', 'set', 'dev', tagged_iface, 'down']),
            call(['ip', 'link', 'delete', tagged_iface]),
            call(['ip', 'link', 'set', 'dev', iface, 'down']),
            call(['ip', 'a']),
            call(['ip', 'ro'])]

        self.assert_by_items(mexecute.call_args_list, execute_stack)
