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

import time

from nailgun.settings import settings


def validate_password_credentials(username, password, **kwargs):
    return (username == settings.FAKE_KEYSTONE_USERNAME and
            password == settings.FAKE_KEYSTONE_PASSWORD)


def validate_token(token):
    return token.startswith('token')


def generate_token():
    return 'token' + str(int(time.time()))
