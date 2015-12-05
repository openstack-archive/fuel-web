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


import alembic

from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


class TestDbMigrations(base.BaseTestCase):

    def test_clean_downgrade(self):
        # We don't have data migration for clusters with vip_name 'ovs'
        # so checking migration only for clean DB
        dropdb()
        alembic.command.upgrade(ALEMBIC_CONFIG, 'head')
        alembic.command.downgrade(ALEMBIC_CONFIG, 'base')
