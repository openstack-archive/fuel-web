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

import copy

from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseAuthenticationIntegrationTest

from nailgun.settings import settings


class TestAuthToken(BaseAuthenticationIntegrationTest):
    """Test the authentication tokens -- using X-Auth-Token header
    and the token=xxx cookie.
    The header has priority over cookie.
    """

    def setUp(self):
        super(TestAuthToken, self).setUp()

        resp = self.app.post(
            '/keystone/v2.0/tokens',
            jsonutils.dumps({
                'auth': {
                    'tenantName': 'admin',
                    'passwordCredentials': {
                        'username': settings.FAKE_KEYSTONE_USERNAME,
                        'password': settings.FAKE_KEYSTONE_PASSWORD,
                    },
                },
            })
        )

        self.token = resp.json['access']['token']['id'].encode('utf-8')
        self.headers = copy.deepcopy(self.default_headers)

    def test_no_token_error(self):
        """Make sure that 401 is raised when no token is provided.
        """
        resp = self.app.get(
            '/api/nodes/allocation/stats',
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(401, resp.status_code)

    def test_x_auth_token_header(self):
        """Check that X-Auth-Token header authentication works.
        """
        self.headers['X-Auth-Token'] = self.token

        resp = self.app.get(
            '/api/nodes/allocation/stats',
            headers=self.headers
        )
        self.assertEqual(200, resp.status_code)

    def test_cookie_token(self):
        """Make sure that Cookie authentication works.
        """
        self.headers['Cookie'] = 'token=%s' % self.token

        resp = self.app.get(
            '/api/nodes/allocation/stats',
            headers=self.headers
        )
        self.assertEqual(200, resp.status_code)

    def test_x_auth_token_header_has_priority_over_cookie(self):
        """Make sure that X-Auth-Token header has priority over the
        Cookie token.
        """
        self.headers['X-Auth-Token'] = self.token
        self.headers['Cookie'] = 'token=xxx'

        resp = self.app.get(
            '/api/nodes/allocation/stats',
            headers=self.headers
        )
        self.assertEqual(200, resp.status_code)

        # Now the other way around
        self.headers['X-Auth-Token'] = 'xxx'
        self.headers['Cookie'] = 'token=%s' % self.token

        resp = self.app.get(
            '/api/nodes/allocation/stats',
            headers=self.headers,
            expect_errors=True
        )
        self.assertEqual(401, resp.status_code)
