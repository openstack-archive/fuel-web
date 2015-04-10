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

import os
import tempfile
import unittest2

from fuel_package_updates.settings import Settings


class TestSetUpKeystoneCreds(unittest2.TestCase):

    settings_yaml = """
    keystone_creds:
        username: {0}
        password: {1}
        tenant_name: {2}
    supported_releases:
        - "2014.2-6.1"
    updates_destinations:
        centos: '/var/www/nailgun/2014.2-6.1/centos/updates'
        ubuntu: '/var/www/nailgun/2014.2-6.1/ubuntu/updates'
    httproot: "/var/www/nailgun"
    port: 8000
    """

    def test_setup_env_variables(self):
        env_username = "TESTING_KEYSTONE_USERNAME"
        env_password = "TESTING_KEYSTONE_PASSWORD"
        env_tenant = "TESTING_KEYSTONE_TENANT"

        username = "Michael"
        password = "admin123"
        tenant = "random_tenant"

        os.environ[env_username] = username
        os.environ[env_password] = password
        os.environ[env_tenant] = tenant

        settings_file = tempfile.mktemp()
        with open(settings_file, 'w') as fd:
            fd.write(self.settings_yaml.format(env_username, env_password,
                                               env_tenant))

        settings = Settings.from_yaml(settings_file)

        self.assertEqual(settings.keystone_creds['username'], username)
        self.assertEqual(settings.keystone_creds['password'], password)
        self.assertEqual(settings.keystone_creds['tenant_name'], tenant)

    def test_not_setup_env_variables(self):
        settings_file = tempfile.mktemp()
        with open(settings_file, 'w') as fd:
            fd.write(self.settings_yaml.format(
                'NOT_SET_USERNAME', 'NOT_SET_PASSWORD', 'NOT_SET_TENANT'))

        settings = Settings.from_yaml(settings_file)

        self.assertEqual(settings.keystone_creds['username'], 'admin')
        self.assertEqual(settings.keystone_creds['password'], 'admin')
        self.assertEqual(settings.keystone_creds['tenant_name'], 'admin')
