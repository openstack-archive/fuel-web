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

import json
import subprocess
import unittest

from network_checker.multicast import api as multicast_api


class TestMulticastVerification(unittest.TestCase):

    def setUp(self):
        self.config_node_112 = {"uid": "112", "group": "225.0.0.250",
                                "port": 8890}
        self.config_node_113 = {"uid": "113", "group": "225.0.0.250",
                                "port": 8890}
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

        self.assertEqual(info_node_112, [u"113", u"112"])
        self.assertEqual(info_node_113, [u"113", u"112"])


class TestSystemMulticastVerification(unittest.TestCase):

    def shell_helper(self, args):
        proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, err = proc.communicate()
        return json.loads(out)

    def test_multicast_verification_with_detach(self):
        init_args = ['fuel-netcheck', 'multicast', 'serve', 'listen']
        listen_data = self.shell_helper(init_args)
        self.assertIn('uid', listen_data)

        args = ['fuel-netcheck', 'multicast', 'send', 'info']
        info = self.shell_helper(args)
        self.assertEqual([listen_data['uid']], info)

        cleanup_args = ['fuel-netcheck', 'multicast', 'clean']
        clean = self.shell_helper(cleanup_args)
        self.assertTrue(clean)

    def test_mutlicast_with_config(self):
        config = {"uid": "112", "group": "225.0.0.250",
                  "port": 8890, "iface": "eth0"}
        config_json = json.dumps(config)

        init_args = ["fuel-netcheck", "multicast", "serve",
                     "--config", config_json]
        self.shell_helper(init_args)

        args = ['fuel-netcheck', 'multicast', 'listen', 'send', 'info']
        info = self.shell_helper(args)
        self.assertEqual([config['uid']], info)

        cleanup_args = ['fuel-netcheck', 'multicast', 'clean']
        clean = self.shell_helper(cleanup_args)
        self.assertTrue(clean)
