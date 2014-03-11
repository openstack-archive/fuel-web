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

import mock

from nailgun.test import base


class VerificationAgentHandler(base.BaseIntegrationTest):

    def setUp(self):
        super(VerificationAgentHandler, self).setUp()
        self.cluster = self.env.create_cluster(False)

    @mock.patch('nailgun.task.manager.CheckNetworksTaskManager.execute')
    def test_verification_check_networks(self, check_execute):
        check_execute.return_value = {'data': 'success'}
        args = (['net1', 'net2'],)
        kwargs = {'check_admin_untagged': True}
        resp = self.app.put(
            base.reverse('VerificationHandler',
                         kwargs={'cluster_id': self.cluster.id}),
            json.dumps({'task_name': 'check_networks',
                        'args': args,
                        'kwargs': kwargs}),
            headers=self.default_headers,
        )
        check_execute.assert_called_once_with(
            ['net1', 'net2'],
            check_admin_untagged=True)
        response_data = json.loads(resp.body)
        self.assertEqual(response_data, check_execute())

    @mock.patch('nailgun.task.manager.VerifyNetworksTaskManager.execute')
    def test_verification_verify_networks(self, verify_execute):
        verify_execute.return_value = {'data': 'success'}
        args = (['net1', 'net2'], ['101', '103', '104'])
        resp = self.app.put(
            base.reverse('VerificationHandler',
                         kwargs={'cluster_id': self.cluster.id}),
            json.dumps({'task_name': 'verify_networks',
                        'args': args}),
            headers=self.default_headers,
        )
        verify_execute.assert_called_once_with(*args)
        response_data = json.loads(resp.body)
        self.assertEqual(response_data, verify_execute())
