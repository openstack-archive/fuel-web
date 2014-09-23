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


login_schema = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'Login',
    'description': 'a JSON that is used as input for login handler',
    'type': 'object',
    'properties': {
        'username': {'type': 'string'},
        'password': {'type': 'string'},
    },
    'required': ['username', 'password'],
}


logout_schema = {
    '$schema': 'http://json-schema.org/draft-04/schema#',
    'title': 'Logout',
    'description': 'a JSON that is used as input for logout handler',
    'type': 'object',
    'properties': {
        'auth_token': {'type': 'string'},
    },
    'required': ['auth_token'],
}
