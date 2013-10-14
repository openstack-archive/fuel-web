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

import csv
from hashlib import md5
import json
from mock import patch
from StringIO import StringIO

from nailgun.api.models import Task
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):
    def _create_capacity_log(self):
        resp = self.app.put(
            reverse('CapacityLogHandler'),
            headers=self.default_headers)
        self.assertEquals(resp.status, 202)

        capacity_task = self.db.query(Task).filter_by(
            name="capacity_log"
        ).first()
        self.env.wait_ready(capacity_task)

    def _get_capacity_log_json(self):
        resp = self.app.get(
            reverse('CapacityLogHandler'),
            headers=self.default_headers
        )
        return json.loads(resp.body)

    @fake_tasks()
    def test_capacity_log_handler(self):
        self.env.create_node(api=False)

        self._create_capacity_log()

        capacity_log = self._get_capacity_log_json()

        for field in ['id', 'report']:
            self.assertTrue(field in capacity_log)

        report = capacity_log['report']

        report_fields = ['fuel_data', 'environment_stats', 'allocation_stats']
        for field in report_fields:
            self.assertTrue(field in report)

        self.assertEquals(report['allocation_stats']['allocated'], 0)
        self.assertEquals(report['allocation_stats']['unallocated'], 1)

    @patch('nailgun.api.handlers.version.settings.VERSION', {
        'release': '0.1b'})
    def test_capacity_csv_checksum(self):
        self._create_capacity_log()
        resp = self.app.get(reverse('CapacityLogCsvHandler'))
        self.assertEquals(200, resp.status)

        response_stream = StringIO(resp.body)
        checksum = md5(''.join(response_stream.readlines()[:-2])).hexdigest()

        response_stream.seek(0)
        csvreader = csv.reader(response_stream, delimiter=',',
                               quotechar='|', quoting=csv.QUOTE_MINIMAL)

        rows = [
            ['Fuel version', '0.1b'],
            ['Fuel UUID', 'Unknown'],
            ['Checksum', checksum],
            ['Environment Name', 'Node Count'],
            ['Total number allocated of nodes', '0'],
            ['Total number of unallocated nodes', '0'],
            ['Node role(s)', 'Number of nodes with this configuration'],
            [],
        ]
        for row in csvreader:
            self.assertTrue(row in rows)
