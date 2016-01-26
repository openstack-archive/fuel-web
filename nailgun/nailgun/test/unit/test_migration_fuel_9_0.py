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
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG

from nailgun import consts
from nailgun.test import base


_prepare_revision = '43b2cb64dae6'
_test_revision = '11a9adc6d36a'


def setup_module(module):
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()

    releaseid = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2014.2.2-6.1',
            'operating_system': 'ubuntu',
            'state': 'available',
            'networks_metadata': jsonutils.dumps({
                'neutron': {
                    'networks': [],
                    'config': {}
                }
            })
        }]
    ).inserted_primary_key[0]

    db.execute(
        meta.tables['clusters'].insert(),
        [
            {
                'name': 'test_env_one',
                'release_id': releaseid,
                'mode': 'ha_compact',
                'status': consts.CLUSTER_STATUSES.new,
                'net_provider': 'neutron',
                'grouping': 'roles',
                'fuel_version': '9.0',
            },
            {
                'name': 'test_env_two',
                'release_id': releaseid,
                'mode': 'ha_compact',
                'status': consts.CLUSTER_STATUSES.operational,
                'net_provider': 'neutron',
                'grouping': 'roles',
                'fuel_version': '9.0',
            }
        ]
    )

    db.commit()


class TestClustersMigration(base.BaseAlembicMigrationTest):

    def test_cluster_has_once_deployed_attr(self):
        result = db.execute(
            sa.select([self.meta.tables['clusters'].c.status,
                       self.meta.tables['clusters'].c.once_deployed])
        ).fetchall()

        for status, once_deployed in result:
            if status == consts.CLUSTER_STATUSES.operational:
                self.assertTrue(once_deployed)
            else:
                self.assertFalse(once_deployed)
