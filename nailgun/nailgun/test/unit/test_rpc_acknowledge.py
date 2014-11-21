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

import mock

from nailgun.errors import errors
from nailgun.rpc import receiverd
from nailgun.test import base


class TestRpcAcknowledge(base.BaseTestCase):

    def setUp(self):
        super(TestRpcAcknowledge, self).setUp()
        self.receiver = mock.Mock()
        self.connection = mock.Mock()
        self.consumer = receiverd.RPCConsumer(self.connection, self.receiver)
        self.msg = mock.Mock()
        self.body = {'method': 'test',
                     'args': {}}

    def test_message_acked_if_success(self):
        self.consumer.consume_msg(self.body, self.msg)
        self.assertEqual(self.msg.ack.call_count, 1)
        self.assertEqual(self.receiver.test.call_count, 1)

    def test_message_acked_if_no_task_found(self):
        self.receiver.test.side_effect = errors.NoTaskFound
        self.consumer.consume_msg(self.body, self.msg)
        self.assertEqual(self.receiver.test.call_count, 1)
        self.assertEqual(self.msg.ack.call_count, 1)

    def test_message_acked_if_exception(self):
        self.receiver.test.side_effect = Exception
        self.consumer.consume_msg(self.body, self.msg)
        self.assertEqual(self.receiver.test.call_count, 1)
        self.assertEqual(self.msg.ack.call_count, 1)

    def test_message_requeued_in_case_of_interrupt(self):
        self.receiver.test.side_effect = KeyboardInterrupt
        self.assertRaises(
            KeyboardInterrupt,
            self.consumer.consume_msg, self.body, self.msg)
        self.assertFalse(self.msg.ack.called)
        self.assertEqual(self.msg.requeue.call_count, 1)
