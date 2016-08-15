# coding: utf-8

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

import alembic

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base
from oslo_serialization import jsonutils
import sqlalchemy as sa

_prepare_revision = 'f2314e5d63c9'
_test_revision = '675105097a69'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)

    prepare()
    db.commit()

    alembic.command.downgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()
    db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2015.1-8.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'networks_metadata': jsonutils.dumps({
                'neutron': {
                    'networks': [],
                    'config': {}
                }
            }),
            'volumes_metadata': jsonutils.dumps(
                {'rule_to_pick_boot_disk': [
                    {'type': 'very_important_rule'}
                ]})
        }])
    db.commit()


class TestDropRulesToPickBootableDisk(base.BaseAlembicMigrationTest):

    def test_drop_rule_to_pick_bootable_disk(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.volumes_metadata])
        ).fetchone()[0]
        volumes_metadata = jsonutils.loads(result)
        self.assertNotIn('rule_to_pick_boot_disk', volumes_metadata)


class TestDeploymentHistorySummaryField(base.BaseAlembicMigrationTest):

    def test_downgrade_tasks_noop(self):
        deployment_history = self.meta.tables['deployment_history']
        self.assertNotIn('summary', deployment_history.c)
