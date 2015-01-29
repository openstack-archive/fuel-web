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
from nailgun.db.sqlalchemy.models import Release
from nailgun.db.sqlalchemy.models import Task
from nailgun.openstack.common import jsonutils
from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import FakeFile
from nailgun.test.base import reverse


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
            resp.body,
            "Can't delete release with "
            "clusters assigned"
        )

    @mock.patch.dict(settings.VERSION, {'feature_groups': ['mirantis']})
    def test_release_put_deployable(self):
        release = self.env.create_release(api=False)

        for deployable in (False, True):
            resp = self.app.put(
                reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
                params=jsonutils.dumps({
                    'is_deployable': deployable,
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
                'is_deployable': False,
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

    @mock.patch.object(settings, 'MASTER_IP', '127.0.0.1')
    def test_release_put_orchestrator_data_w_masks(self):
        release = self.env.create_release(api=False)

        orchestrator_data = {
            'repo_metadata': {
                '5.1': 'http://{MASTER_IP}:8080/centos/x86_64',
                '5.1-user': 'http://{MASTER_IP}:8080/centos-user/x86_64',
            },
            'puppet_modules_source': 'rsync://{MASTER_IP}:/puppet/modules/',
            'puppet_manifests_source': 'rsync://{MASTER_IP}:/puppet/manifests/'
        }

        resp = self.app.put(
            reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
            params=jsonutils.dumps({'orchestrator_data': orchestrator_data}),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)

        resp = self.app.get(
            reverse('ReleaseHandler', kwargs={'obj_id': release.id}),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        orchestrator_data = resp.json_body['orchestrator_data']

        self.assertEqual(orchestrator_data['repo_metadata'], {
            '5.1': 'http://127.0.0.1:8080/centos/x86_64',
            '5.1-user': 'http://127.0.0.1:8080/centos-user/x86_64'})
        self.assertEqual(
            orchestrator_data['puppet_modules_source'],
            'rsync://127.0.0.1:/puppet/modules/')
        self.assertEqual(
            orchestrator_data['puppet_manifests_source'],
            'rsync://127.0.0.1:/puppet/manifests/')


class TestReleaseUploadISO(BaseIntegrationTest):

    def setUp(self):
        super(TestReleaseUploadISO, self).setUp()
        self.release = self.env.create_release(
            state=consts.RELEASE_STATES.unavailable)

    def _put(self, data, release_id=None):
        release_id = release_id or self.release.id
        return self.app.put(
            reverse('ReleaseUploadISO', kwargs={'obj_id': release_id}),
            params=data,
            headers=self.default_headers,
            expect_errors=True)

    def test_release_not_found(self):
        resp = self._put('paydata', release_id=42)

        self.assertEqual(404, resp.status_code)
        self.assertRegexpMatches(resp.body, 'Release not found')

    def test_successfull_uploading(self):
        output = FakeFile()

        # we need to mock output in order to be sure that the all content
        # we pass will be saved properly
        open_fn = 'nailgun.api.v1.handlers.release.open'
        mopen = mock.mock_open()
        mopen.return_value = output
        with mock.patch(open_fn, mopen, create=True):
            resp = self._put('image bytestream')

        # check that the file was written with correct data
        self.assertEqual(output.getvalue(), 'image bytestream')

        # check release outcome
        self.assertEqual(202, resp.status_code)
        self.assertEqual(self.release.state, consts.RELEASE_STATES.processing)

        # test that task was properly created
        task = self.db.query(Task).filter_by(
            uuid=resp.json_body['uuid']).first()
        self.assertEqual(task.release_id, self.release.id)
        self.assertEqual(task.name, consts.TASK_NAMES.prepare_release)
        self.assertEqual(task.status, consts.TASK_STATUSES.running)

    def test_concurrent_request_conflict(self):
        # we need to perform one successful upload in order to
        # change release's state to 'processing'
        self.test_successfull_uploading()

        # .. and now we're going to perform a new one and check
        # that it's forbidden
        resp = self._put('new image bytestream')
        self.assertEqual(409, resp.status_code)

    def test_not_allowed_for_available_release(self):
        self.release = self.env.create_release(
            state=consts.RELEASE_STATES.available)

        resp = self._put('new image bytestream')
        self.assertEqual(405, resp.status_code)

    # def test_checksum_fail(self):
    #     # we need to mock in order to do not create real file
    #     # in /tmp
    #     open_fn = 'nailgun.api.v1.handlers.release.open'
    #     with mock.patch(open_fn, mock.mock_open(), create=True):
    #         resp = self._put('image bytestream')

    #     # check release outcome
    #     self.assertEqual(400, resp.status_code)
    #     self.assertEqual(
    #         self.release.state, consts.RELEASE_STATES.unavailable)
