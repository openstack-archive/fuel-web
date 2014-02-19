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

import unittest

from dhcp_checker import multicast


class TestMulticast(unittest.TestCase):

    def test_multicast(self):
        group = '225.0.0.250'
        port = 8123
        node_id = '111'
        ttl = 1

        results = multicast.multicast(group, port, node_id, ttl)

        self.assertEqual(results, (node_id, [node_id]))
