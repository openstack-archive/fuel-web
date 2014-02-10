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

from nailgun.assassin import assassind
from nailgun.test.base import BaseIntegrationTest


class TestKeepalive(BaseIntegrationTest):

    VERY_LONG_TIMEOUT = 60 * 60  # 1 hour
    ZERO_TIMEOUT = 0

    def test_node_becomes_offline(self):
        node = self.env.create_node(
            status="discover",
            roles=["controller"],
            name="Dead or alive"
        )
        assassind.update_nodes_status(self.VERY_LONG_TIMEOUT)
        self.assertEqual(node.online, True)
        assassind.update_nodes_status(self.ZERO_TIMEOUT)
        self.assertEqual(node.online, False)

    def test_provisioning_node_not_becomes_offline(self):
        node = self.env.create_node(
            status="provisioning",
            roles=["controller"],
            name="Dead or alive"
        )
        assassind.update_nodes_status(self.ZERO_TIMEOUT)
        self.assertEqual(node.online, True)
