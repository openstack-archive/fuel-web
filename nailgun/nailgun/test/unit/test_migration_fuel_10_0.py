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

_prepare_revision = '675105097a69'
_test_revision = 'c6edea552f1e'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    pass


class TestTasksSnapshotField(base.BaseAlembicMigrationTest):
    def test_fields_exist(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [{
                'uuid': 'fake_task_uuid_0',
                'name': 'dump',
                'status': 'pending',
                'tasks_snapshot': '[{"id":"taskid","type":"puppet"}]'
            }]
        )
        result = db.execute(
            sa.select([
                self.meta.tables['tasks'].c.tasks_snapshot,
            ])
        ).first()
        self.assertIsNotNone(result['tasks_snapshot'])
