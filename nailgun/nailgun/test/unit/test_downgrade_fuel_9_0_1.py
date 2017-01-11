# Copyright 2016 Mirantis, Inc.
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

import datetime

import alembic

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base
import sqlalchemy as sa


_prepare_revision = '675105097a69'
_test_revision = '11a9adc6d36a'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)

    prepare()
    db.commit()

    alembic.command.downgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()
    TestNodeErrorMessageDowngrade.prepare(meta)


class TestNodeErrorMessageDowngrade(base.BaseAlembicMigrationTest):
    node_uuid = '26b508d0-0d76-4159-bce9-f67ec2765480'
    long_error_msg = 'a' * 500

    @classmethod
    def prepare(cls, meta):
        nodes = meta.tables['nodes']

        db.execute(
            nodes.insert(),
            [{
                'uuid': cls.node_uuid,
                'cluster_id': None,
                'group_id': None,
                'status': 'discover',
                'meta': '{}',
                'mac': 'aa:aa:aa:aa:aa:aa',
                'error_msg': cls.long_error_msg,
                'timestamp': datetime.datetime.utcnow(),
            }]
        )

    def test_downgrade_node_error_msg(self):
        nodes = self.meta.tables['nodes']
        self.assertIsInstance(nodes.columns['error_msg'].type, sa.String)

        node = db.query(nodes).filter_by(uuid=self.node_uuid).first()
        self.assertEqual(node.error_msg, self.long_error_msg[:255])
