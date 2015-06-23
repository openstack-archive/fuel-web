# -*- coding: utf-8 -*-

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

from mock import patch
from oslo.serialization import jsonutils

from nailgun.test.base import BaseAuthenticationIntegrationTest
from nailgun.utils import reverse


class TestPublicHandlers(BaseAuthenticationIntegrationTest):

    def test_node_agent_api(self):
        self.env.create_node(
            api=False,
            status='provisioning',
            meta=self.env.default_metadata()
        )
        node_db = self.env.nodes[0]
        resp = self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps(
                {'mac': node_db.mac,
                 'status': 'discover', 'manufacturer': 'new'}
            ),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.app.post(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps({'mac': self.env.generate_random_mac(),
                            'status': 'discover'}),
            headers=self.default_headers)

        self.assertEqual(201, resp.status_code)

    def test_version_api(self):
        resp = self.app.get(
            reverse('VersionHandler'),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)

    @patch('nailgun.api.v1.handlers.version.utils.get_fuel_release_versions')
    def test_500_no_html_dev(self, handler_get):
        exc_text = "Here goes an exception"
        handler_get.side_effect = Exception(exc_text)
        resp = self.app.get(
            reverse('VersionHandler'),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(500, resp.status_code)
        self.assertIn(exc_text, resp.body)
        self.assertIn("Traceback", resp.body)
        self.assertNotIn("html", resp.body)

    @patch('nailgun.api.v1.handlers.version.utils.get_fuel_release_versions')
    def test_500_no_html_production(self, handler_get):
        exc_text = "Here goes an exception"
        handler_get.side_effect = Exception(exc_text)
        with patch('nailgun.settings.settings.DEVELOPMENT', 0):
            resp = self.app.get(
                reverse('VersionHandler'),
                headers=self.default_headers,
                expect_errors=True
            )
        self.assertEqual(500, resp.status_code)
        self.assertEqual(exc_text, resp.body)
