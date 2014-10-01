# -*- coding: utf-8 -*-

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
from mock import patch
from StringIO import StringIO

from nailgun.db.sqlalchemy.models import Task
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):
    def _create_capacity_log(self):
        resp = self.app.put(
            reverse('CapacityLogHandler'),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 202)

        capacity_task = self.db.query(Task).filter_by(
            name="capacity_log"
        ).first()
        self.env.wait_ready(capacity_task)

    def _get_capacity_log_json(self):
        resp = self.app.get(
            reverse('CapacityLogHandler'),
            headers=self.default_headers
        )
        return resp.json_body

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

        self.assertEqual(report['allocation_stats']['allocated'], 0)
        self.assertEqual(report['allocation_stats']['unallocated'], 1)

    @patch('nailgun.api.v1.handlers.version.settings.VERSION', {
        'release': '0.1b'})
    def test_capacity_csv_checksum(self):
        self._create_capacity_log()
        resp = self.app.get(reverse('CapacityLogCsvHandler'))
        self.assertEqual(200, resp.status_code)

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

    @fake_tasks()
    def test_capacity_nodes_allocation(self):
        self.env.create(
            cluster_kwargs={
                'name': 'test_name'
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller', 'cinder'], 'pending_addition': True},
                {'roles': ['compute', 'cinder'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}
            ]
        )
        deployment_task = self.env.launch_deployment()
        self.env.wait_ready(deployment_task)

        self._create_capacity_log()
        capacity_log = self._get_capacity_log_json()
        report = capacity_log['report']

        self.assertEqual(report['allocation_stats']['allocated'], 6)
        self.assertEqual(report['allocation_stats']['unallocated'], 0)

        self.assertEqual(report['roles_stat']['controller'], 2)
        self.assertEqual(report['roles_stat']['cinder+controller'], 1)
        self.assertEqual(report['roles_stat']['cinder+compute'], 1)
        self.assertEqual(report['roles_stat']['compute'], 1)
        self.assertEqual(report['roles_stat']['cinder'], 1)

        self.assertEqual(len(report['environment_stats']), 1)
        test_env = report['environment_stats'][0]
        self.assertEqual(test_env['cluster'], 'test_name')
        self.assertEqual(test_env['nodes'], 6)

    @fake_tasks(godmode=True)
    def test_capacity_csv_log_with_unicode(self):
        self.env.create(
            cluster_kwargs={
                'name': u'тест'
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}
            ]
        )
        deployment_task = self.env.launch_deployment()
        self.env.wait_ready(deployment_task)

        self._create_capacity_log()
        resp = self.app.get(reverse('CapacityLogCsvHandler'))
        self.assertEqual(200, resp.status_code)
