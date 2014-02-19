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

import os
import unittest


class BaseMcollectActionTest(unittest.TestCase):

    def setUp(self):
        self.request_file = '/tmp/mco_request'
        self.reply_file = '/tmp/mco_reply'
        os.environ['MCOLLECTIVE_REPLY_FILE'] = self.reply_file
        os.environ['MCOLLECTIVE_REQUEST_FILE'] = self.request_file

    def tearDown(self):
        if os.path.exists(self.request_file):
            os.unlink(self.request_file)
        if os.path.exists(self.reply_file):
            os.unlink(self.reply_file)
