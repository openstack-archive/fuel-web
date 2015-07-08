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
from nailgun.utils import reverse
from oslo.serialization import jsonutils


class TestAssignmentHandlers(BaseIntegrationTest):
    def test_dashboard_entries_list_empty(self):
        cluster = self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[{}]
        )

        resp = self.app.get(
            reverse(
                'DashboardEntryCollectionHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual([], resp.json_body)

    def test_dashboard_entry_creation(self):
        cluster = self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[{}]
        )

        title = 'test title'
        url = 'http://test.com/url'
        description = 'short description'
        resp = self.app.post(
            reverse(
                'DashboardEntryCollectionHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            params=jsonutils.dumps({
                "title": title,
                "url": url,
                "description": description
            }),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 201)

        dashboard_entry = self.env.clusters[0].dashboard_entries[0]
        self.assertEqual(dashboard_entry.title, title)
        self.assertEqual(dashboard_entry.url, url)
        self.assertEqual(dashboard_entry.description, description)

    def test_dashboard_entry_fail_creation(self):
        cluster = self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[{}]
        )

        title = 'test title'
        description = 'short description'

        resp = self.app.post(
            reverse(
                'DashboardEntryCollectionHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            jsonutils.dumps({
                'title': title,
                'description': description
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(self.env.clusters[0].dashboard_entries), 0)
