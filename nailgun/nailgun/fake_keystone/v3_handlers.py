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

import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import validate
from nailgun.fake_keystone import generate_token
from nailgun.fake_keystone import validate_password_credentials
from nailgun.fake_keystone import validate_token
from nailgun.settings import settings


class TokensHandler(BaseHandler):

    @handle_errors
    @validate
    @serialize
    def GET(self):
        token = web.ctx.env.get('HTTP_X_SUBJECT_TOKEN', '')
        if not validate_token(token):
            raise self.http(401)

        return self._get_token_info()

    @handle_errors
    @validate
    @serialize
    def POST(self):
        data = self.checked_data()
        try:
            if 'password' in data['auth']['identity']['methods']:
                if not validate_password_credentials(
                    data['auth']['identity']['password']['user']['name'],
                    data['auth']['identity']['password']['user']['password']
                ):
                    raise self.http(401)
            elif 'token' in data['auth']['identity']['methods']:
                if not validate_token(data['auth']['identity']['token']['id']):
                    raise self.http(401)
            else:
                raise self.http(400)
        except (KeyError, TypeError):
            raise self.http(400)

        web.header('X-Subject-Token', generate_token())

        return self._get_token_info()

    def _get_token_info(self):
        return {
            "token": {
                "methods": ["password"],
                "issued_at": "2016-09-29T13:06:37.620739Z",
                "expires_at": "2016-09-29T19:06:37.620687Z",
                "roles": [{"name": settings.FAKE_KEYSTONE_ROLE}],
                "project": {
                    "domain": {"id": "123", "name": "fuel"},
                    "id": "456",
                    "name": "admin"
                },
                "user": {
                    "domain": {"id": "123", "name": "fuel"},
                    "id": "789",
                    "name": "admin"
                },
                "catalog": [],
                "audit_ids": ["CZGk7nPaRF-PzmokqvKcDQ"]
            }
        }

    def DELETE(self):
        raise self.http(204)


class VersionHandler(BaseHandler):

    @handle_errors
    @validate
    @serialize
    def GET(self):
        keystone_href = 'http://{ip_addr}:{port}/keystone/v3/'.format(
            ip_addr=settings.LISTEN_ADDRESS, port=settings.LISTEN_PORT)
        return {
            "version": {
                "id": "v3.6",
                "status": "stable",
                "updated": "2016-04-04T00:00:00Z",
                "media-types": [{
                    "base": "application/json",
                    "type": "application/vnd.openstack.identity-v3+json"
                }],
                "links": [{"href": keystone_href, "rel": "self"}]
            }
        }
