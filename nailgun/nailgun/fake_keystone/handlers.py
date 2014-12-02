# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content
from nailgun.fake_keystone import generate_token
from nailgun.fake_keystone import validate_password_credentials
from nailgun.fake_keystone import validate_token
from nailgun.settings import settings


class TokensHandler(BaseHandler):

    @content
    def POST(self):
        data = self.checked_data()
        try:
            if 'passwordCredentials' in data['auth']:
                if not validate_password_credentials(
                        **data['auth']['passwordCredentials']):
                    raise self.http(401)
            elif 'token' in data['auth']:
                if not validate_token(data['auth']['token']['id']):
                    raise self.http(401)
            else:
                raise self.http(400)
        except (KeyError, TypeError):
            raise self.http(400)

        token = generate_token()

        return {
            "access": {
                "token": {
                    "issued_at": "2012-07-10T13:37:58.708765",
                    "expires": "2012-07-10T14:37:58Z",
                    "id": token,
                    "tenant": {
                        "description": None,
                        "enabled": True,
                        "id": "12345",
                        "name": "admin"
                    }
                },
                "serviceCatalog": [],
                "user": {
                    "username": "admin",
                    "roles_links": [],
                    "id": "9876",
                    "roles": [{"name": "admin"}],
                    "name": "admin"
                },
                "metadata": {
                    "is_admin": 0,
                    "roles": ["4567"]
                }
            }
        }


class VersionHandler(BaseHandler):

    @content
    def GET(self):
        keystone_href = 'http://{ip_addr}:{port}/keystone/v2.0/'.format(
            ip_addr=settings.LISTEN_ADDRESS, port=settings.LISTEN_PORT)
        return {
            'version': {
                'id': 'v2.0',
                'status': 'stable',
                'updated': '2014-04-17T00:00:00Z',
                'links': [
                    {
                        'rel': 'self',
                        'href': keystone_href,
                    }, {
                        'rel': 'describedby',
                        'type': 'text/html',
                        'href': 'http://docs.openstack.org/',
                    },
                ],
                'media-types': [
                    {
                        'base': 'application/json',
                        'type': 'application/vnd.openstack.identity-v2.0+json',
                    }, {
                        'base': 'application/xml',
                        'type': 'application/vnd.openstack.identity-v2.0+xml',
                    },
                ],
            },
        }
