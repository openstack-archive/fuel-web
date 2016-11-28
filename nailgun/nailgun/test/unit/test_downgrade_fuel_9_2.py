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

ROLES_META = {
    'controller': {
        'tags': [
            'controller',
            'rabbitmq',
            'database',
            'keystone',
            'neutron'
        ]
    }
}

PLUGIN_ROLE_META = {
    'test_plugin_role': {
        'tags': ['test_plugin_tag']
    }
}

PLUGIN_TAGS_META = {
    'test_plugin_tag':
        {'has_primary': False}
}

TAGS_META = {
    'controller': {
        'has_primary': True,
    },
    'rabbitmq': {
        'has_primary': True
    },
    'database': {
        'has_primary': True
    },
    'keystone': {
        'has_primary': True
    },
    'neutron': {
        'has_primary': True
    }
}


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.downgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()
    plugin = {
        'name': 'Test_P',
        'version': '3.0.0',
        'title': 'Test Plugin',
        'package_version': '5.0.0',
        'roles_metadata': jsonutils.dumps(PLUGIN_ROLE_META),
        'tags_metadata': jsonutils.dumps(PLUGIN_TAGS_META)
    }
    result = db.execute(meta.tables['plugins'].insert(), [plugin])

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2016.1-10.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'deployment_tasks': '[]',
            'roles_metadata': jsonutils.dumps(ROLES_META),
            'tags_matadata': jsonutils.dumps(TAGS_META),
            'is_deployable': True,
            'networks_metadata': '{}',
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
            'roles_metadata': jsonutils.dumps(ROLES_META),
            'tags_metadata': '{}',
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


class TestTags(base.BaseAlembicMigrationTest):
    def test_primary_tags_downgrade(self):
        nodes = self.meta.tables['nodes']
        query = sa.select([nodes.c.primary_roles]).where(
            nodes.c.uuid == 'fcd49872-3917-4a18-98f9-3f5acfe3fdec')
        primary_roles = db.execute(query).fetchone()[0]
        self.assertItemsEqual(primary_roles, ['role_y'])

    def test_downgrade_tags_metadata(self):
        releases = self.meta.tables['releases']
        self.assertNotIn('tags_metadata', releases.c._all_columns)

        clusters = self.meta.tables['clusters']
        self.assertNotIn('tags_metadata', clusters.c._all_columns)
        self.assertNotIn('roles_metadata', clusters.c._all_columns)

        plugins = self.meta.tables['plugins']
        self.assertNotIn('tags_metadata', plugins.c._all_columns)

    def test_downgrade_field_tags_from_roles(self):
        releases = self.meta.tables['releases']
        query = sa.select([releases.c.roles_metadata])
        for role_meta in db.execute(query).fetchall():
            self.assertNotIn('tags', role_meta)

        plugins = self.meta.tables['plugins']
        query = sa.select([plugins.c.roles_metadata])
        for role_meta in db.execute(query):
            self.assertNotIn('tags', role_meta)
