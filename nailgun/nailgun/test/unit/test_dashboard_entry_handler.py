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
from nailgun.db import db
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse
from oslo.serialization import jsonutils

class TestHandlers(BaseIntegrationTest):

    def test_dashboard_entry_put_change_title_and_url_and_description(self):
        cluster = self.env.create_cluster(api=False)
        dashboard_entry_from_db = DashboardEntry()

        dashboard_entry_from_db.title = 'title'
        dashboard_entry_from_db.url = 'url'
        dashboard_entry_from_db.description = 'description'
        dashboard_entry_from_db.cluster_id = cluster['id']

        db().add(dashboard_entry_from_db)
        db().flush()

        new_title = 'new title 2'
        new_url = 'http://new_url.test/url2'
        new_description = 'new description 2'

        resp = self.app.put(
            reverse(
                'DashboardEntryHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            params=jsonutils.dumps({
                "title": new_title,
                "url": new_url,
                "description": new_description
            }),
            headers=self.default_headers
        )

        self.assertEqual(200, resp.status_code)
        self.db.refresh(dashboard_entry_from_db)
        self.assertEqual(new_title, dashboard_entry_from_db.title)
        self.assertEqual(new_url, dashboard_entry_from_db.url)
        self.assertEqual(new_description, dashboard_entry_from_db.description)

    # def test_release_put_returns_400_if_no_body(self):
    #     release = self.env.create_release(api=False)
    #     resp = self.app.put(
    #         reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
    #         "",
    #         headers=self.default_headers,
    #         expect_errors=True)
    #     self.assertEqual(resp.status_code, 400)
    #
    # def test_release_delete_returns_400_if_clusters(self):
    #     cluster = self.env.create_cluster(api=False)
    #     resp = self.app.delete(
    #         reverse('ReleaseHandler',
    #                 kwargs={'obj_id': cluster.release.id}),
    #         headers=self.default_headers,
    #         expect_errors=True
    #     )
    #     self.assertEqual(resp.status_code, 400)
    #     self.assertEqual(
    #         resp.json_body["message"],
    #         "Can't delete release with "
    #         "clusters assigned"
    #     )
    #
    # @mock.patch.dict(settings.VERSION, {'feature_groups': ['mirantis']})
    # def test_release_put_deployable(self):
    #     release = self.env.create_release(api=False)
    #
    #     for deployable in (False, True):
    #         resp = self.app.put(
    #             reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
    #             params=jsonutils.dumps({
    #                 'is_deployable': deployable,
    #             }),
    #             headers=self.default_headers)
    #         self.assertEqual(200, resp.status_code)
    #         self.assertEqual(resp.json_body['is_deployable'], deployable)
    #
    # @mock.patch.dict(settings.VERSION, {'feature_groups': ['experimental']})
    # def test_release_deployable_in_experimental(self):
    #     # set deployable to False
    #     release = self.env.create_release(api=False)
    #     resp = self.app.put(
    #         reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
    #         params=jsonutils.dumps({
    #             'is_deployable': False,
    #         }),
    #         headers=self.default_headers)
    #     self.assertEqual(200, resp.status_code)
    #
    #     # check that release is deployable
    #     resp = self.app.get(
    #         reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
    #         headers=self.default_headers,
    #     )
    #     self.assertEqual(200, resp.status_code)
    #     self.assertEqual(resp.json_body['is_deployable'], True)
