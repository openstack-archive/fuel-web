#    Copyright 2016 Mirantis, Inc.
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

import copy

from oslo_serialization import jsonutils

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestReleaseAttributesMetadataHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestReleaseAttributesMetadataHandlers, self).setUp()
        self.release = self.env.create_release()

    def test_get(self):
        resp = self.app.get(
            reverse('ReleaseAttributesMetadataHandler',
                    kwargs={'obj_id': self.release.id}),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.release['attributes_metadata'],
                         resp.json)

    def test_put(self):
        data = copy.deepcopy(self.release['attributes_metadata'])
        data['editable']['repo_setup']['repos']['value'] = 'foo'
        resp = self.app.put(
            reverse('ReleaseAttributesMetadataHandler',
                    kwargs={'obj_id': self.release.id}),
            jsonutils.dumps(data),
            headers=self.default_headers,
        )
        new_editable = self.release['attributes_metadata']['editable']
        self.assertEqual(new_editable['repo_setup']['repos']['value'], 'foo')
        self.assertEqual(resp.status_code, 200)

    def test_put_wrong_data(self):
        del self.release['attributes_metadata']['editable']
        data = jsonutils.dumps(self.release['attributes_metadata'])
        resp = self.app.put(
            reverse('ReleaseAttributesMetadataHandler',
                    kwargs={'obj_id': self.release.id}),
            data,
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
