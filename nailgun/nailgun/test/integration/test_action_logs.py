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

import datetime

from nailgun import consts
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestActionLogs(BaseIntegrationTest):

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

        action_logs = objects.ActionLogCollection.filter_by(
            None, action_type=consts.ACTION_TYPES.nailgun_task)
        for al in action_logs:
            task_status = al.additional_info["ended_with_status"]
            self.assertEqual(task_status, consts.TASK_STATUSES.ready)

    @fake_tasks()
    def test_only_utc_datetime_used(self):
        start_dt = datetime.datetime.utcnow()
        self.env.create(
            api=True,
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
            ]
        )

        deployment_task = self.env.launch_deployment()
        self.env.wait_ready(deployment_task)

        cluster = self.env.clusters[0]
        self.app.delete(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            headers=self.default_headers
        )

        end_dt = datetime.datetime.utcnow()
        action_logs = objects.ActionLogCollection.filter_by(None)

        for action_log in action_logs:
            self.assertLessEqual(start_dt, action_log.start_timestamp)
            self.assertLessEqual(start_dt, action_log.end_timestamp)
            self.assertGreaterEqual(end_dt, action_log.start_timestamp)
            self.assertGreaterEqual(end_dt, action_log.end_timestamp)

    @fake_tasks()
    def test_all_action_logs_types_saved(self):
        # Creating nailgun_tasks
        self.env.create(
            api=True,
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
            ]
        )

        deployment_task = self.env.launch_deployment()
        self.env.wait_ready(deployment_task)

        # Creating http_request
        cluster = self.env.clusters[0]
        self.app.delete(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            headers=self.default_headers
        )

        # Filtering action types
        action_logs = objects.ActionLogCollection.filter_by(None)
        action_types = [al.action_type for al in action_logs]
        self.assertSetEqual(set(consts.ACTION_TYPES), set(action_types))
