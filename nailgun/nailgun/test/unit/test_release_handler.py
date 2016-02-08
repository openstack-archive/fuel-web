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

import mock
from nailgun import consts
from oslo_serialization import jsonutils

from nailgun.db.sqlalchemy.models import Release
from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def test_release_put_change_name_and_version(self):
        release = self.env.create_release(api=False)
        resp = self.app.put(
            reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
            params=jsonutils.dumps({
                'name': 'modified release',
                'version': '5.1'
            }),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(200, resp.status_code)
        release_from_db = self.db.query(Release).one()
        self.db.refresh(release_from_db)
        self.assertEqual('5.1', release_from_db.version)
        self.assertEqual('5.1', resp.json_body['version'])
        self.assertEqual('modified release', resp.json_body['name'])

    def test_release_put_returns_400_if_no_body(self):
        release = self.env.create_release(api=False)
        resp = self.app.put(
            reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
            "",
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_release_delete_returns_400_if_clusters(self):
        cluster = self.env.create_cluster(api=False)
        resp = self.app.delete(
            reverse('ReleaseHandler',
                    kwargs={'obj_id': cluster.release.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body["message"],
            "Can't delete release with "
            "clusters assigned"
        )

    @mock.patch.dict(settings.VERSION, {'feature_groups': []})
    def test_release_put_deployable(self):
        release = self.env.create_release(api=False)

        for state, deployable in (
            ('available', True),
            ('unavailable', False),
            ('manageonly', False)
        ):
            resp = self.app.put(
                reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
                params=jsonutils.dumps({
                    'state': state,
                }),
                headers=self.default_headers)
            self.assertEqual(200, resp.status_code)
            self.assertEqual(resp.json_body['is_deployable'], deployable)

    @mock.patch.dict(settings.VERSION, {'feature_groups': ['experimental']})
    def test_release_deployable_in_experimental(self):
        # set deployable to False
        release = self.env.create_release(api=False)
        resp = self.app.put(
            reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
            params=jsonutils.dumps({
                'state': consts.RELEASE_STATES.manageonly,
            }),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)

        # check that release is deployable
        resp = self.app.get(
            reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
            headers=self.default_headers,
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json_body['is_deployable'], True)

    @mock.patch.dict(settings.VERSION, {'feature_groups': ['experimental']})
    def test_unavailable_release_not_deployable_in_experimental(self):
        # set deployable to False and state to 'unavailable'
        release = self.env.create_release(api=False)
        resp = self.app.put(
            reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
            params=jsonutils.dumps({
                'state': consts.RELEASE_STATES.unavailable
            }),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)

        # check that release is deployable
        resp = self.app.get(
            reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
            headers=self.default_headers,
        )

        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json_body['is_deployable'], False)
