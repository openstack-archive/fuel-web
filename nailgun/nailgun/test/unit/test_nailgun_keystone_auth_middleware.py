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

import mock
import webob

from nailgun.middleware.keystone import NailgunFakeKeystoneAuthMiddleware
from nailgun.middleware.keystone import NailgunKeystoneAuthMiddleware
from nailgun.test.base import BaseUnitTest


@mock.patch('nailgun.middleware.keystone.public_urls')
class AuthMiddlewareTestBase(object):
    """Base Test class that holds common tests for
    NailgunKeystoneAuthMiddleware and NailgunFakeKeystoneAuthMiddleware
    """

    MiddlewareClass = None

    def setUp(self):
        self.app = mock.Mock()
        self.fake_start_response = mock.Mock()
        super(AuthMiddlewareTestBase, self).setUp()

    def get_middleware(self):
        return self.MiddlewareClass(self.app)

    def test_do_not_verify_public_urls_and_methods(self, mock_public_urls):
        mock_public_urls.return_value = {
            '/public-url': ['GET', 'POST']
        }

        fake_req = webob.Request.blank('/public-url', method='POST')
        middleware = self.get_middleware()
        middleware(fake_req.environ, self.fake_start_response)

        self.assertTrue(self.app.called)
        self.app.assert_called_with(fake_req.environ, self.fake_start_response)
        self.assertTrue(fake_req.environ['is_public_api'])

    def test_verify_non_public_urls(self, mock_public_urls):
        mock_public_urls.return_value = {
            '/public-url': ['GET']
        }

        fake_req = webob.Request.blank('/non-pubilc')
        middleware = self.get_middleware()
        middleware(fake_req.environ, self.fake_start_response)

        self.assertFalse(self.app.called)
        self.assertFalse(fake_req.environ['is_public_api'])

    def test_verify_non_public_method_on_public_url(self, mock_public_urls):
        mock_public_urls.return_value = {
            '/public-url': ['GET']
        }
        fake_req = webob.Request.blank('/public-url', method='PUT')
        middleware = self.get_middleware()
        middleware(fake_req.environ, self.fake_start_response)

        self.assertFalse(self.app.called)
        self.assertFalse(fake_req.environ['is_public_api'])

    def test_raise_error_on_invalid_route_regexp(self, mock_public_urls):
        mock_public_urls.return_value = {
            '[bad-regexp(': ['GET']
        }
        with self.assertRaisesRegexp(Exception,
                                     'Cannot compile public API routes'):
            self.get_middleware()


class TestFakeKeystoneAuthMiddleware(AuthMiddlewareTestBase, BaseUnitTest):
    MiddlewareClass = NailgunFakeKeystoneAuthMiddleware

    @mock.patch('nailgun.middleware.keystone.validate_token')
    def test_401_on_invalid_token(self, mock_invalid_token):
        mock_invalid_token.return_value = False

        fake_req = webob.Request.blank('/non-public-url')
        middleware = self.get_middleware()
        middleware(fake_req.environ, self.fake_start_response)

        self.fake_start_response.assert_called_with('401 Unauthorized', [])

    @mock.patch('nailgun.middleware.keystone.validate_token')
    def test_token_is_valid(self, mock_invalid_token):
        mock_invalid_token.return_value = True

        fake_req = webob.Request.blank('/non-public-url')
        middleware = self.get_middleware()
        middleware(fake_req.environ, self.fake_start_response)

        self.assertTrue(self.app.called)
        self.app.assert_called_with(fake_req.environ, self.fake_start_response)


class TestKeystoneAuthMiddleware(AuthMiddlewareTestBase, BaseUnitTest):
    MiddlewareClass = NailgunKeystoneAuthMiddleware
