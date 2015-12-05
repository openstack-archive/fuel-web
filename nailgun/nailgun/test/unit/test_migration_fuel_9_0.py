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
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '43b2cb64dae6'
_test_revision = '11a9adc6d36a'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)
    prepare()


def prepare():
    meta = base.reflect_db_metadata()

    db.execute(
        meta.tables['ip_addrs'].insert(),
        [{
            'ip_addr': '192.168.0.2',
            'vip_name': 'vrouter',
            'is_user_defined': True,
        }])

    db.commit()


class TestVipMigration(base.BaseAlembicMigrationTest):
    def test_ip_addrs_vip_name_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['ip_addrs'].c.vip_name]))
        self.assertEqual(result.scalar(), "vrouter")

    def test_ip_addrs_user_assigned_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['ip_addrs'].c.is_user_defined]))
        self.assertEqual(result.scalar(), True)
