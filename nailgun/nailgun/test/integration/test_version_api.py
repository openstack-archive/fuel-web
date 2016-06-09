# -*- coding: utf-8 -*-

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

from mock import patch

from nailgun.test.base import BaseAuthenticationIntegrationTest
from nailgun.test.base import reverse


class TestVersionApi(BaseAuthenticationIntegrationTest):
    """Test the version api

    Test the version api to make sure it requires authentication
    and works when passed a valid auth token.
    """

    def setUp(self):
        super(TestVersionApi, self).setUp()
        self.token = self.get_auth_token()
        self.headers = copy.deepcopy(self.default_headers)

    def test_version_api_noauth(self):
        """Check that version api requires auth."""
        resp = self.app.get(
            reverse('VersionHandler'),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(401, resp.status_code)

    def test_version_api_auth(self):
        """Check that version api works with auth."""
        self.headers['X-Auth-Token'] = self.token
        resp = self.app.get(
            reverse('VersionHandler'),
            headers=self.headers
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

