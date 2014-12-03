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

from nailgun.db.sqlalchemy import utils
from nailgun.test import base


class TestDbUtils(base.BaseUnitTest):

    def setUp(self):
        super(TestDbUtils, self).setUp()
        self.default_settings = {
            'engine': 'db_engine',
            'host': 'localhost',
            'port': '8080',
            'name': 'database',
            'user': 'db_user',
            'passwd': 'db_pass',
        }

    def test_make_dsn_with_regular_host(self):
        dsn = utils.make_dsn(**self.default_settings)
        self.assertEqual(
            dsn,
            'db_engine://db_user:db_pass@localhost:8080/database'
        )

    def test_make_dsn_with_socket(self):
        self.default_settings['host'] = '/path/to/socket'
        dsn = utils.make_dsn(**self.default_settings)
        self.assertEqual(
            dsn,
            'db_engine://db_user:db_pass@/database?host=/path/to/socket'
        )
