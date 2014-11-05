#    Copyright 2014 Mirantis, Inc.
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


from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestReleaseNetworksHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestReleaseNetworksHandlers, self).setUp()
        self.release = self.env.create_release()

    def test_get(self):
        resp = self.app.get(
            reverse('ReleaseNetworksHandler',
                    kwargs={'obj_id': self.release.id}),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.release['networks_metadata'], resp.json)

    def test_post(self):
        resp = self.app.post(
            reverse('ReleaseNetworksHandler',
                    kwargs={'obj_id': self.release.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 405)

    def test_delete(self):
        resp = self.app.delete(
            reverse('ReleaseNetworksHandler',
                    kwargs={'obj_id': self.release.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 405)

    def test_put(self):
        data = jsonutils.dumps(self.release['networks_metadata'])
        resp = self.app.put(
            reverse('ReleaseNetworksHandler',
                    kwargs={'obj_id': self.release.id}),
            data,
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
