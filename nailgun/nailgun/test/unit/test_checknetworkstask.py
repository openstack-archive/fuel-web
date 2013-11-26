# -*- coding: utf-8 -*-

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

from netaddr import IPNetwork
from netaddr import IPRange

from nailgun.network.manager import NetworkManager
from nailgun.test.base import BaseIntegrationTest


class TestHandlers(BaseIntegrationTest):
    def test_ip_range_intersection(self):
        nm = NetworkManager
        self.assertEqual(nm.is_range_intersection(
            IPRange('192.168.0.0', '192.168.255.255'),
            IPNetwork('192.168.1.0/24')
        ), True)
        self.assertEqual(nm.is_range_intersection(
            IPRange('164.174.47.1', '191.0.0.0'),
            IPNetwork('192.168.1.0/24')
        ), False)
        self.assertEqual(nm.is_range_intersection(
            IPRange('192.168.0.0', '192.168.255.255'),
            IPRange('164.174.47.1', '191.0.0.0')
        ), False)
        self.assertEqual(nm.is_range_intersection(
            IPNetwork('192.168.1.0/8'),
            IPNetwork('192.168.1.0/24')
        ), True)
        self.assertEqual(nm.is_range_intersection(
            IPRange('192.168.0.0', '192.168.130.255'),
            IPRange('192.168.128.0', '192.168.255.255'),
        ), True)

        self.assertEqual(nm.is_cidr_intersection(
            IPNetwork('192.168.0.0/20'),
            IPNetwork('192.168.1.0/24')
        ), True)
        self.assertEqual(nm.is_cidr_intersection(
            IPNetwork('164.164.0.0/14'),
            IPNetwork('192.168.1.0/24')
        ), False)
        self.assertEqual(nm.is_cidr_intersection(
            IPNetwork('164.174.47.0/25'),
            IPNetwork('164.174.47.128/25')
        ), False)
        self.assertEqual(nm.is_cidr_intersection(
            IPNetwork('192.168.1.0/8'),
            IPNetwork('192.168.1.0/24')
        ), True)
