# -*- coding: utf-8 -*-

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

import netaddr

from nailgun.network import utils
from nailgun.test.base import BaseUnitTest


class TestNetworkUtils(BaseUnitTest):

    def test_compare_two_macs(self):
        equal_macs = (
            ('00-1B-77-49-54-FD', '00-1B-77-49-54-FD'),
            ('00-1B-77-49-54-FD', '00-1b-77-49-54-fd'),
            ('00-1B-77-49-54-FD', '001b:7749:54fd'),
            ('00-1B-77-49-54-FD', '1B:7749:54FD'),
            ('00-1B-77-49-54-FD', '001b774954fd'),
            ('00-1B-77-49-54-FD', netaddr.EUI('00-1B-77-49-54-FD')),
            ('aa:bb:cc:dd:ee:0f', 'aa:bb:cc:dd:ee:f'),
        )

        for mac1, mac2 in equal_macs:
            self.assertTrue(utils.is_same_mac(mac1, mac2))

        self.assertFalse(
            utils.is_same_mac('AA-BB-CC-11-22-33', '11:22:33:AA:BB:CC'))

    def test_compare_macs_raise_exception(self):
        with self.assertRaises(ValueError):
            utils.is_same_mac('QWERTY', 'ASDF')
