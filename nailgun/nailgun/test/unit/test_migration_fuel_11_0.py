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

import datetime

import alembic
from oslo_serialization import jsonutils
import six
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base
from nailgun.utils.migration import is_feature_supported

_prepare_revision = 'c6edea552f1e'
_test_revision = 'dc8bc8751c42'

# version of Fuel when tags was introduced
FUEL_TAGS_SUPPORT = '9.0'

NEW_ROLES_META = {
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

NEW_TAGS_LIST = [
    'rabbitmq',
    'database',
    'keystone',
    'neutron'
]


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name0',
            'version': '2015.1-8.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'roles': jsonutils.dumps([
                'controller',
            ]),
            'roles_metadata': jsonutils.dumps({
                'controller': {
                    'name': 'Controller',
                    'has_primary': True
                },
                'compute': {
                    'name': 'Compute'
                },
            }),
            'is_deployable': True
        }])

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name1',
            'version': '2016.1-11.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'roles': jsonutils.dumps([
                'controller',
            ]),
            'roles_metadata': jsonutils.dumps({
                'controller': {
                    'name': 'Controller',
                    'has_primary': True
                },
                'compute': {
                    'name': 'Compute'
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
            'primary_roles': ['role_y'],
            'meta': '{}',
            'mac': 'bb:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
        }]
    )

    db.commit()


class TestTags(base.BaseAlembicMigrationTest):
    def test_primary_tags_migration(self):
        nodes = self.meta.tables['nodes']
        query = sa.select([nodes.c.primary_tags]).where(
            nodes.c.uuid == 'fcd49872-3917-4a18-98f9-3f5acfe3fdec')
        primary_tags = db.execute(query).fetchone()[0]
        self.assertItemsEqual(primary_tags, ['role_y'])

    def test_tags_meta_migration(self):
        releases = self.meta.tables['releases']
        query = sa.select([releases.c.roles_metadata,
                           releases.c.tags_metadata])
        for roles_meta, tags_meta in db.execute(query):
            tags_meta = jsonutils.loads(tags_meta)
            for role_name, role_meta in six.iteritems(
                    jsonutils.loads(roles_meta)):
                self.assertEqual(
                    tags_meta[role_name].get('has_primary', False),
                    role_meta.get('has_primary', False)
                )

    def test_tags_migration_for_supported_releases(self):
        releases = self.meta.tables['releases']
        query = sa.select([releases.c.version,
                           releases.c.roles_metadata,
                           releases.c.tags_metadata])
        for version, roles_meta, tags_meta in db.execute(query):

            if not is_feature_supported(version, FUEL_TAGS_SUPPORT):
                continue

            roles_meta = jsonutils.loads(roles_meta)
            for role_name, role_meta in six.iteritems(NEW_ROLES_META):
                self.assertItemsEqual(
                    roles_meta[role_name]['tags'],
                    role_meta['tags']
                )
            tags_meta = jsonutils.loads(tags_meta)
            missing_tags = set(NEW_TAGS_LIST) - set(tags_meta)
            self.assertEqual(len(missing_tags), 0)

    def test_tags_migration_for_not_supported_releases(self):
        releases = self.meta.tables['releases']
        query = sa.select([releases.c.version,
                           releases.c.roles_metadata,
                           releases.c.tags_metadata])
        for version, roles_meta, tags_meta in db.execute(query):

            if is_feature_supported(version, FUEL_TAGS_SUPPORT):
                continue

            roles_meta = jsonutils.loads(roles_meta)
            for role_name, role_meta in six.iteritems(NEW_ROLES_META):
                common_tags = (set(role_meta['tags']) &
                               set(roles_meta[role_name]['tags']))
                # common tag 'controller' for backward compatibility
                self.assertEqual(len(common_tags), 1)
            tags_meta = jsonutils.loads(tags_meta)
            wrong_tags = set(NEW_TAGS_LIST) - set(tags_meta)
            self.assertNotEqual(len(wrong_tags), 0)
