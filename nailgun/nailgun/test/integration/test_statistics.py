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

from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class TestActionLogsProcessing(BaseIntegrationTest):

    @fake_tasks()
    def test_action_log_updating_for_tasks(self):
        meta1 = self.env.generate_interfaces_in_meta(2)
        mac1 = meta1['interfaces'][0]['mac']
        meta2 = self.env.generate_interfaces_in_meta(2)
        mac2 = meta2['interfaces'][0]['mac']

        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": True, "meta": meta1, "mac": mac1},
                {"api": True, "meta": meta2, "mac": mac2},
            ]
        )

        task = self.env.launch_verify_networks()
        self.env.wait_ready(task, 30)

        action_logs = self.db.query(models.ActionLog).all()
        for al in action_logs:
            task_status = al.additional_info["ended_with_status"]
            self.assertEqual(task_status, consts.TASK_STATUSES.ready)
