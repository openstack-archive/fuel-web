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

import Cookie
import re

from nailgun.api.v1 import urls as api_urls
from nailgun.fake_keystone import validate_token
from nailgun.settings import settings

from keystonemiddleware import auth_token


def public_urls():
    urls = {}
    for url, methods in api_urls.public_urls().iteritems():
        urls['{0}{1}'.format('/api/v1', url)] = methods
        urls['{0}{1}'.format('/api', url)] = methods
    urls["/$"] = ['GET']
    urls["/static"] = ['GET']
    urls["/keystone"] = ['GET', 'POST']
    return urls


class CookieTokenMixin(object):
    """Mixin for getting the auth token out of request X-Auth-Token header or
    if that doesn't exist, from the cookie.
    """
    def get_auth_token(self, env):
        token = env.get('HTTP_X_AUTH_TOKEN', '')

        if token:
            return token

        c = Cookie.SimpleCookie(env.get('HTTP_COOKIE', ''))

        token = c.get('token')

        if token:
            return token.value

        return ''


class SkipAuthMixin(object):
    """Mixin which skips verification of authentication tokens for public
    routes in the API.
    """
    def __init__(self, app):
        self.public_api_routes = {}
        self.app = app
        try:
            for route_tpl, methods in public_urls().iteritems():
                self.public_api_routes[re.compile(route_tpl)] = methods
        except re.error as e:
            msg = 'Cannot compile public API routes: {0}'.format(e)
            raise Exception(msg)

        super(SkipAuthMixin, self).__init__(app, settings.AUTH)

    def __call__(self, env, start_response):
        path = env.get('PATH_INFO', '/')
        method = env.get('REQUEST_METHOD')

        # The information whether the API call is being performed against the
        # public API may be useful. Saving it to the
        # WSGI environment is reasonable thereby.
        env['is_public_api'] = False
        for pattern, methods in self.public_api_routes.iteritems():
            if re.match(pattern, path):
                if method in methods:
                    env['is_public_api'] = True
                    break

        if env['is_public_api']:
            return self.app(env, start_response)
        return super(SkipAuthMixin, self).__call__(env, start_response)


class FakeAuthProtocol(CookieTokenMixin):
    """Auth protocol for fake mode.
    """
    def __init__(self, app, conf):
        self.app = app

    def __call__(self, env, start_response):
        if validate_token(self.get_auth_token(env)):
            return self.app(env, start_response)
        else:
            start_response('401 Unauthorized', [])
            return ['']


class NailgunKeystoneAuthMiddleware(
        CookieTokenMixin,
        SkipAuthMixin,
        auth_token.AuthProtocol):
    """Auth middleware for keystone.
    """
    def __call__(self, env, start_response):
        token = self.get_auth_token(env)

        if token:
            env['HTTP_X_AUTH_TOKEN'] = token

        return super(
            NailgunKeystoneAuthMiddleware,
            self
        ).__call__(env, start_response)


class NailgunFakeKeystoneAuthMiddleware(SkipAuthMixin, FakeAuthProtocol):
    """Auth middleware for fake mode.
    """
    pass
