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

import mock
import webob

from nailgun.middleware.rbac_middleware import RBACMiddleware
from nailgun.test.base import BaseUnitTest


class TestRBACMiddleware(BaseUnitTest):
    """Class that holds unit tests for RBACMiddleware."""

    modification_methods = ('POST', 'PUT', 'DELETE', 'PATCH')

    def setUp(self):
        self.app = mock.Mock()
        self.fake_start_response = mock.Mock()
        super(TestRBACMiddleware, self).setUp()

    def test_public_request(self):
        """RBAC middleware should not affect public requests."""
        middleware = RBACMiddleware(self.app)

        fake_req = webob.Request.blank('/test-url')
        fake_req.environ['is_public_api'] = True

        middleware(fake_req.environ, self.fake_start_response)

        self.assertTrue(self.app.called)

    def test_admin_request(self):
        """The user with 'admin' role has permissions to send any request.

        He should have the total control
        over the environments.
        """
        middleware = RBACMiddleware(self.app)

        http_methods = list(self.modification_methods)
        http_methods.append('GET')
        for method in http_methods:
            fake_req = webob.Request.blank('/test-url', method=method)
            fake_req.environ['is_public_api'] = False
            fake_req.environ['HTTP_X_ROLES'] = 'writer, reader, admin'

            middleware(fake_req.environ, self.fake_start_response)

            self.assertTrue(self.app.called)

    def test_non_admin_get_request(self):
        """Non-admin user should have permissions for read actions."""
        middleware = RBACMiddleware(self.app)

        fake_req = webob.Request.blank('/test-url', method='GET')
        fake_req.environ['is_public_api'] = False
        fake_req.environ['HTTP_X_ROLES'] = ''

        middleware(fake_req.environ, self.fake_start_response)

        self.assertTrue(self.app.called)

    def test_non_admin_common_request(self):
        """Non-admin user has read-only permissions.

        He should not have opportunity to change
        any settings in the environments.
        """
        middleware = RBACMiddleware(self.app)

        for method in self.modification_methods:
            fake_req = webob.Request.blank('/test-url', method=method)
            fake_req.environ['is_public_api'] = False
            fake_req.environ['HTTP_X_ROLES'] = 'reader'

            middleware(fake_req.environ, self.fake_start_response)

            self.fake_start_response.\
                assert_called_with('403 Permission Denied', [])
