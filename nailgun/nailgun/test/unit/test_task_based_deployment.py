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
import six

from nailgun import consts
from nailgun.test.base import BaseUnitTest
from nailgun.orchestrator import task_based_deployment
from nailgun.orchestrator import tasks_serializer


class TestDeploymentTaskSerializer(BaseUnitTest):
    def make_task(self, task_id, task_type="puppet"):
        return mock.MagicMock(id=task_id, type=task_type)

    def test_get_stage_serializer(self):
        factory = task_based_deployment.DeploymentTaskSerializer()
        self.assertIs(
            task_based_deployment.CreateVMsOnCompute,
            factory.get_stage_serializer(
                self.make_task("generate_vms")
            )
        )

        self.assertIs(
            task_based_deployment.NoopSerializer,
            factory.get_stage_serializer(
                self.make_task("upload_repos", "stage")
            )
        )
        self.assertIs(
            task_based_deployment.NoopSerializer,
            factory.get_stage_serializer(
                self.make_task("upload_repos", "skipped")
            )
        )
        self.assertIs(
            tasks_serializer.
        )
    # def get_stage_serializer(self, task):
    #     if task.get('type') in self.noop_task_types:
    #         return NoopSerializer
    #     return super(DeploymentTaskSerializer, self).get_stage_serializer(
    #         task
    #     )
