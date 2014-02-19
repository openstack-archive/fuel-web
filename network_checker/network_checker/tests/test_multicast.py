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

from network_checker import api
from network_checker.multicast import api as multicast_api


class TestMulticastVerification(unittest.TestCase):

    def setUp(self):
        self.config_node_112 = {"node_id": "112", "group": "225.0.0.250",
                                "port": 8890, 'timeout': 3}
        self.config_node_113 = {"node_id": "113", "group": "225.0.0.250",
                                "port": 8890, 'timeout': 3}
        self.mchecker_node_112 = multicast_api.MulticastChecker(
            **self.config_node_112)
        self.mchecker_node_113 = multicast_api.MulticastChecker(
            **self.config_node_113)

    def test_multicast_verification(self):
        self.mchecker_node_112.listen()
        self.mchecker_node_113.listen()
        self.mchecker_node_112.send()
        self.mchecker_node_113.send()

        info_node_112 = self.mchecker_node_112.get_info()
        info_node_113 = self.mchecker_node_113.get_info()

        self.assertEqual(info_node_112, ("112", ["112", "113"]))
        self.assertEqual(info_node_113, ("113", ["112", "113"]))


class TestFullMulticastVerification(unittest.TestCase):

    def setUp(self):
        self.config = {"node_id": "112", "group": "225.0.0.250",
                       "port": 8890, 'timeout': 3}
        self.mchecker = multicast_api.MulticastChecker(**self.config)

    def test_multicast_verification_with_detach(self):
        listen_response = api.Api.listen(self.mchecker)
        self.assertEqual(listen_response, 'Listener started.')

        sender_response = api.Api.send(self.mchecker)
        self.assertEqual(sender_response, 'Sended data.')

        get_info_response = api.Api.get_info(self.mchecker)
        self.assertEqual(get_info_response, '["112", ["112"]]')
