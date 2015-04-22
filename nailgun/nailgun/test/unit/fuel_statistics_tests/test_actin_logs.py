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
from nailgun.test.base import BaseTestCase
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestActionLogs(BaseTestCase):

    @fake_tasks()
    def test_action_logs_date(self):
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

        action_logs = objects.ActionLogCollection.filter_by(None)

        dt = datetime.datetime.utcnow()
        for action_log in action_logs:
            self.assertGreaterEqual(dt, action_log.start_timestamp)
            self.assertGreaterEqual(dt, action_log.end_timestamp)

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
        self.assertItemsEqual(set(consts.ACTION_TYPES), set(action_types))
