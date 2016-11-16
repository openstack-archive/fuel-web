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

import datetime

import alembic
from oslo_serialization import jsonutils

import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '3763c404ca48'
_test_revision = 'f2314e5d63c9'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.downgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2016.1-11.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'roles': jsonutils.dumps([
                'controller',
            ]),
            'roles_metadata': jsonutils.dumps({
                'controller': {
                    'name': 'Controller',
                },
            }),
            'is_deployable': True
        }])

    release_id = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test_env1',
            'release_id': release_id,
            'mode': 'ha_compact',
            'status': 'operational',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '10.0',
        }])
    cluster_id = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['nodes'].insert(),
        [{
            'uuid': 'fcd49872-3917-4a18-98f9-3f5acfe3fdec',
            'cluster_id': cluster_id,
            'group_id': None,
            'status': 'ready',
            'roles': ['role_x', 'role_y'],
            'primary_tags': ['role_y', 'test'],
            'meta': '{}',
            'mac': 'bb:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
        }]
    )

    db.commit()


class TestPluginTags(base.BaseAlembicMigrationTest):
    def test_primary_tags_downgrade(self):
        nodes = self.meta.tables['nodes']
        query = sa.select([nodes.c.primary_roles]).where(
            nodes.c.uuid == 'fcd49872-3917-4a18-98f9-3f5acfe3fdec')
        primary_roles = db.execute(query).fetchone()[0]
        self.assertItemsEqual(primary_roles, ['role_y'])
