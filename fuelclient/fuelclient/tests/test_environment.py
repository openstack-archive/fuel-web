# -*- coding: utf-8 -*-
#
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

from fuelclient.objects.environment import Environment
from fuelclient.tests import base


class TestEnvironmentOstf(base.UnitTestCase):

    def setUp(self):
        super(TestEnvironmentOstf, self).setUp()

        self.env = Environment(None)

    @mock.patch.object(Environment.connection, 'post_request', mock.Mock(
        return_value=[
            {'id': 1},
            {'id': 2}, ]))
    def test_run_test_sets(self):
        self.assertEqual(self.env._testruns_ids, [])

        testruns = self.env.run_test_sets(['sanity', 'ha'])

        self.assertEqual(len(testruns), 2)
        self.assertIn(1, self.env._testruns_ids)
        self.assertIn(2, self.env._testruns_ids)

    @mock.patch.object(Environment.connection, 'get_request', mock.Mock(
        side_effect=[
            {'id': 1, 'status': 'running'},
            {'id': 2, 'status': 'finished'}, ]))
    def test_get_state_of_tests(self):
        self.env._testruns_ids.extend([1, 2])
        tests = self.env.get_state_of_tests()

        self.env.connection.get_request.assert_has_calls([
            mock.call('testruns/1', ostf=True),
            mock.call('testruns/2', ostf=True)])
        self.assertEqual(tests, [
            {'id': 1, 'status': 'running'},
            {'id': 2, 'status': 'finished'}])
