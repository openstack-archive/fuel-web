# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

"""
Product info handlers
"""
import pecan

from nailgun.api.v2.controllers.base import BaseController
from nailgun.fake_keystone import generate_token
from nailgun.fake_keystone import validate_password_credentials
from nailgun.fake_keystone import validate_token


class TokensController(BaseController):
    @pecan.expose(template='json:', content_type='application/json')
    def post(self):
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
                raise self.http(400, 'No passwordCredentials nor token given')
        except (KeyError, TypeError) as e:
            raise self.http(400, e.message)

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


class FakeKeystoneV20Controller(BaseController):
    tokens = TokensController()


class FakeKeystoneController(BaseController):
    v20 = FakeKeystoneV20Controller()

    @pecan.expose()
    def _route(self, args, request):
        if args[0] == 'v2.0':
            args[0] = 'v20'
        return super(FakeKeystoneController, self)._route(args, request)
