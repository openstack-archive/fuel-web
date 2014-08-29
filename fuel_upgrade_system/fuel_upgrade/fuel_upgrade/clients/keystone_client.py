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

import json
import logging
import requests

logger = logging.getLogger(__name__)


class KeystoneClient(object):
    """Simple keystone authentification client

    :param str username: is user name
    :param str password: is user password
    :param str auth_url: authentification url
    :param str tenant_name: tenant name
    """

    def __init__(self, username=None, password=None,
                 auth_url=None, tenant_name=None):
        self.auth_url = auth_url
        self.tenant_name = tenant_name
        self.username = username
        self.password = password

    @property
    def request(self):
        """Creates authentification session if required

        :returns: :class:`requests.Session` object
        """
        session = requests.Session()
        token = self.get_token()
        if token:
            session.headers.update({'X-Auth-Token': token})

        return session

    def get_token(self):
        """Retrieves auth token from keystone

        :returns: authentification token or None in case of error

        NOTE(eli): for 5.0.x versions of fuel we don't
        have keystone and fuel access control feature,
        as result this client should work with and without
        authentication, in order to do this, we are
        trying to create Keystone client and in case if
        it fails we don't use authentication
        """
        try:
            resp = requests.post(
                self.auth_url,
                headers={'content-type': 'application/json'},
                data=json.dumps({
                    'auth': {
                        'tenantName': self.tenant_name,
                        'passwordCredentials': {
                            'username': self.username,
                            'password': self.password}}})).json()

            return (isinstance(resp, dict) and
                    resp.get('access', {}).get('token', {}).get('id'))
        except (ValueError, requests.exceptions.RequestException) as exc:
            logger.debug('Cannot authenticate in keystone: {0}'.format(exc))

        return None
