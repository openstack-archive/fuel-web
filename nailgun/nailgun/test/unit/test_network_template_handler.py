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

from oslo_serialization import jsonutils

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def get_template(self, cluster_id, expect_errors=False):
        resp = self.app.get(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster_id}
            ),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

        return resp

    def test_network_template_upload(self):
        cluster = self.env.create_cluster(api=False)
        template = self.env.read_fixtures(['network_template'])[0]
        resp = self.app.put(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id},
            ),
            jsonutils.dumps(template),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)

        resp = self.get_template(cluster.id)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(template, resp.json_body)

    def test_wrong_network_template_upload_failed(self):
        cluster = self.env.create_cluster(api=False)
        template = self.env.read_fixtures(['network_template'])[0]
        template['adv_net_template']['default'] = {}
        resp = self.app.put(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id},
            ),
            jsonutils.dumps(template),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    def test_template_not_set(self):
        resp = self.get_template(1, expect_errors=True)
        self.assertEqual(404, resp.status_code)

    def test_delete_template(self):
        cluster = self.env.create_cluster(api=False)
        template = self.env.read_fixtures(['network_template'])[0]
        resp = self.app.put(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id},
            ),
            jsonutils.dumps(template),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)

        resp = self.app.delete(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id},
            ),
            headers=self.default_headers
        )
        self.assertEquals(204, resp.status_code)

        resp = self.get_template(cluster.id)
        self.assertEquals(None, resp.json_body)
