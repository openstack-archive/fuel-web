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

    @fake_tasks()
    def test_task_deploy_used_if_option_enabled(self):
        self.cluster.attributes.editable['common']['task_deploy'] = True
        task = self.env.launch_deployment()
        self.env.wait_ready(task)
