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

import requests

import keystoneclient.client
import keystoneclient.exceptions

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content_json

from nailgun.api.v1.validators.auth import LoginValidator
from nailgun.api.v1.validators.auth import LogoutValidator

from nailgun.settings import settings


class LoginHandler(BaseHandler):
    """Authenticates a given user and returns an auth token.

    Request example::

        POST /auth/login

        {
            "username": "admin",
            "password": "admin"
        }

    Response example::

        {
            "auth_token": "a-token"
        }
    """

    validator = LoginValidator

    _keystone_url = 'http://{0}:{1}/keystone/'.format(settings.MASTER_IP, 8000)
    _tenant = 'admin'

    @content_json
    def POST(self):
        data = self.checked_data()

        keystone = keystoneclient.client.Client(
            username=data['username'],
            password=data['password'],
            auth_url=self._keystone_url,
            tenant_name=self._tenant)

        try:
            keystone.authenticate()
        except keystoneclient.exceptions.Unauthorized:
            return {
                'error': (
                    'Cannot authorize a user with given credentials. '
                    'Please make sure that username and password are correct.')
            }

        return {'auth_token': keystone.auth_token}


class LogoutHandler(BaseHandler):
    """Revoke a given auth token.

    Request example::

        POST /auth/logout

        {
            "auth_token": "a token"
        }
    """

    validator = LogoutValidator

    _keystone_url = 'http://{0}:{1}/keystone/'.format(settings.MASTER_IP, 8000)

    def POST(self):
        data = self.checked_data()

        # Revoke permissions for a given token. Please note, the permissions
        # will not be revoked immediatly because of memcached.
        requests.delete(
            '{0}v2.0/tokens/{1}'.format(
                self._keystone_url, data['auth_token']),

            headers={
                'X-Auth-Token': data['auth_token']}
        )
