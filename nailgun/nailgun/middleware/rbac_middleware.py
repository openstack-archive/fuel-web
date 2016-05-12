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


class RBACMiddleware(object):
    """Role based authentication control middleware for keystone.

    Separates the privileges for users with 'admin' role and without it.
    Non-admin users have only read permissions.
    """
    permitted_uris = ['/api/settings']

    def __init__(self, app):
        self.app = app

    def __call__(self, env, start_response):
        if not env['is_public_api']:
            method = env['REQUEST_METHOD']

            path = env.get('PATH_INFO', '/')
            is_permitted_uri = path in self.permitted_uris

            roles = env['HTTP_X_ROLES'].split(',')
            is_admin = 'admin' in [role.strip().lower() for role in roles]

            if not is_admin and method != 'GET' and not is_permitted_uri:
                start_response('403 Permission Denied', [])
                return ['You do not have the administrator rights']

        return self.app(env, start_response)
