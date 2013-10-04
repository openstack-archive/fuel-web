#    Copyright 2013 Mirantis, Inc.
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

from nailgun.api.models import Task
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):
    @fake_tasks()
    def test_capacity_log_handler(self):
        self.env.create_node(api=False)

        resp = self.app.put(
            reverse('CapacityLogHandler'),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEquals(resp.status, 202)

        capacity_task = self.db.query(Task).filter_by(
            name="capacity_log"
        ).first()
        self.env.wait_ready(capacity_task)

        resp = self.app.get(
            reverse('CapacityLogHandler'),
            headers=self.default_headers
        )
        response = json.loads(resp.body)

        for field in ['id', 'report']:
            self.assertTrue(field in response)

        report = response['report']

        report_fields = ['fuel_data', 'environment_stats', 'allocation_stats']
        for field in report_fields:
            self.assertTrue(field in report)

        self.assertEquals(report['allocation_stats']['allocated'], 0)
        self.assertEquals(report['allocation_stats']['unallocated'], 1)
