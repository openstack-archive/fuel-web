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

import alembic
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '11a9adc6d36a'
_test_revision = '675105097a69'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    pass


class TestDeploymentHistoryMigration(base.BaseAlembicMigrationTest):
    def test_history_has_task_name_status_idx_index(self):
        tbl = self.meta.tables['deployment_history']
        self.assertIn('deployment_history_task_name_status_idx',
                      [i.name for i in tbl.indexes])


class TestTransactionsNames(base.BaseAlembicMigrationTest):
    def setUp(self):
        super(TestTransactionsNames, self).setUp()

        db.execute(
            self.meta.tables['tasks'].insert(),
            [
                {
                    'uuid': 'fake_task_uuid_0',
                    'name': 'dry_run_deployment',
                    'status': 'pending'
                },
                {
                    'uuid': 'fake_task_uuid_1',
                    'name': 'noop_deployment',
                    'status': 'pending'
                }
            ]
        )

    def test_fields_exist(self):
        result = db.execute(
            sa.select([
                self.meta.tables['tasks'].c.name,
            ])
        ).fetchall()
        self.assertItemsEqual(
            result,
            [('dry_run_deployment', ), ('noop_deployment', )])
