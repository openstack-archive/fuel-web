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

from nailgun.db.sqlalchemy.models.dashboard_entry import DashboardEntry
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse
from oslo.serialization import jsonutils


class TestHandlers(BaseIntegrationTest):

    def test_dashboard_entry_update(self):
        cluster = self.env.create_cluster(api=False)
        dashboard_entry = self.env \
            .create_dashboard_entry(cluster_id=cluster.id)

        dashboard_entry_update = {
            'title': 'new title 2',
            'description': 'new description 2'
        }

        resp = self.app.put(
            reverse(
                'DashboardEntryHandler',
                kwargs={'cluster_id': cluster['id'],
                        'obj_id': dashboard_entry.id}
            ),
            jsonutils.dumps(dashboard_entry_update),
            headers=self.default_headers
        )
        self.assertEqual(dashboard_entry.id, resp.json_body['id'])
        self.assertEqual('new title 2', resp.json_body['title'])
        self.assertEqual('new description 2', resp.json_body['description'])
        self.assertEqual(dashboard_entry.url, resp.json_body['url'])

    def test_dashboard_entry_get_with_cluster(self):
        cluster = self.env.create_cluster(api=False)
        dashboard_entry = self.env \
            .create_dashboard_entry(cluster_id=cluster.id)

        resp = self.app.get(
            reverse(
                'DashboardEntryHandler',
                kwargs={'cluster_id': cluster['id'],
                        'obj_id': dashboard_entry.id}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(dashboard_entry.id, resp.json_body['id'])
        self.assertEqual(dashboard_entry.title, resp.json_body['title'])
        self.assertEqual(dashboard_entry.url, resp.json_body['url'])
        self.assertEqual(dashboard_entry.description,
                         resp.json_body['description'])

    def test_dashboard_entry_not_found(self):
        cluster = self.env.create_cluster(api=False)
        dashboard_entry = self.env \
            .create_dashboard_entry(cluster_id=cluster.id)
        resp = self.app.get(
            reverse(
                'DashboardEntryHandler',
                kwargs={'cluster_id': cluster['id'],
                        'obj_id': dashboard_entry.id + 1}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(404, resp.status_code)

    def test_dashboard_entry_delete(self):
        cluster = self.env.create_cluster(api=False)
        dashboard_entry = self.env \
            .create_dashboard_entry(cluster_id=cluster.id)
        resp = self.app.delete(
            reverse(
                'DashboardEntryHandler',
                kwargs={'cluster_id': cluster['id'],
                        'obj_id': dashboard_entry.id}
            ),
            headers=self.default_headers,
        )
        self.assertEqual(204, resp.status_code)

        d_e_query = self.db.query(DashboardEntry) \
            .filter_by(cluster_id=cluster.id)
        self.assertEquals(d_e_query.count(), 0)
