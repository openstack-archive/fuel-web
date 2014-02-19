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

from network_checker import api
from network_checker.tests import base


class TestMulticastMcollectiveAction(base.BaseMcollectActionTest):

    def setUp(self):
        super(TestMulticastMcollectiveAction, self).setUp()
        config = {self.node_uid: {"group": "225.0.0.250",
                  "port": 8890, 'timeout': 3, 'uid': self.node_uid}}
        self.request = {'data': {
            'config': config, 'check': 'multicast', 'command': None}}

    def perform_start_action(self):
        self.request['data']['command'] = 'listen'

        with open(self.request_file, 'w') as f:
            f.write(json.dumps(self.request))

        api.mcollective()

        with open(self.reply_file) as f:
            data = json.loads(f.read())

        self.assertIsInstance(data, dict)
        self.assertEqual(data['status'], 'inprogress')

    def perform_send_action(self):
        self.request['data']['command'] = 'send'

        with open(self.request_file, 'w') as f:
            f.write(json.dumps(self.request))

        api.mcollective()

        with open(self.reply_file) as f:
            data = json.loads(f.read())

        self.assertIsInstance(data, dict)
        self.assertEqual(data['status'], 'inprogress')

    def perform_get_info_action(self):
        self.request['data']['command'] = 'get_info'

        with open(self.request_file, 'w') as f:
            f.write(json.dumps(self.request))

        api.mcollective()

        with open(self.reply_file) as f:
            data = json.loads(f.read())

        self.assertIsInstance(data, dict)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(json.loads(data['data']), [u'101'])

    def test_mcollective_multicast_flow(self):
        self.perform_start_action()
        self.perform_send_action()
        self.perform_get_info_action()
