# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

from nailgun import consts
from nailgun.errors import errors
from nailgun.orchestrator.task_based_deploy import TasksSerializer
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class TestTaskDeploy(BaseIntegrationTest):
    def setUp(self):
        super(TestTaskDeploy, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {"name": "First",
                 "pending_addition": True},
                {"name": "Second",
                 "roles": ["compute"],
                 "pending_addition": True}
            ]
        )
        self.cluster = self.env.clusters[-1]

    @fake_tasks(mock_rpc=False, fake_rpc=False)
    @mock.patch('nailgun.rpc.cast')
    def get_deploy_message(self, rpc_cast):
        task = self.env.launch_deployment()
        self.assertNotEqual(consts.TASK_STATUSES.error, task.status)
        args, kwargs = rpc_cast.call_args
        return args[1][1]

    @mock.patch.object(TasksSerializer, "ensure_task_based_deploy_allowed")
    def test_task_deploy_used_if_option_enabled(self, _):
        self.cluster.attributes.editable['common']['task_deploy'] = True
        message = self.get_deploy_message()
        self.assertEqual("task_deploy", message["method"])
        self.assertItemsEqual(
            ["task_uuid", "deployment_info", "deployment_tasks"],
            message["args"]
        )

    @mock.patch.object(TasksSerializer, "ensure_task_based_deploy_allowed")
    def test_fallback_to_granular_deploy(self, ensure_allowed):
        ensure_allowed.side_effect = errors.TaskBaseDeploymentNotAllowed
        self.cluster.attributes.editable['common']['task_deploy'] = True
        message = self.get_deploy_message()
        self.assertEqual("granular_deploy", message["method"])
        self.assertItemsEqual(
            ["task_uuid", "deployment_info",
             "pre_deployment", "post_deployment"],
            message["args"]
        )

    def test_granular_deploy_if_not_enabled(self):
        self.cluster.attributes.editable['common']['task_deploy'] = False
        message = self.get_deploy_message()
        self.assertEqual("granular_deploy", message["method"])
        self.assertItemsEqual(
            ["task_uuid", "deployment_info",
             "pre_deployment", "post_deployment"],
            message["args"]
        )
