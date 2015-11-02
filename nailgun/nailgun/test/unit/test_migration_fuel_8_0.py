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
import six
import sqlalchemy as sa
from sqlalchemy.exc import DataError
from sqlalchemy.exc import IntegrityError
import uuid

from nailgun import consts
from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


_prepare_revision = '1e50a4903910'
_test_revision = '43b2cb64dae6'


def setup_module(module):
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()
    db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin',
            'title': 'Test plugin',
            'version': '1.0.0',
            'description': 'Test plugin for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '3.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['8.0']),
        }])

    releaseid = insert_table_row(
        meta.tables['releases'],
        {
            'name': 'test_name',
            'version': '2014.2.2-6.1',
            'operating_system': 'ubuntu',
            'state': 'available'
        }
    )

    clusterid = insert_table_row(
        meta.tables['clusters'],
        {
            'name': 'test_env',
            'release_id': releaseid,
            'mode': 'ha_compact',
            'status': 'new',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '7.0',
        }
    )

    db.execute(
        meta.tables['nodegroups'].insert(),
        [
            {'cluster_id': clusterid, 'name': 'test_nodegroup_a'},
            {'cluster_id': clusterid, 'name': 'test_nodegroup_a'},
            {'cluster_id': clusterid, 'name': 'test_nodegroup_b'},
            {'cluster_id': clusterid, 'name': 'test_nodegroup_b'},
        ])

    db.commit()


def insert_table_row(table, row_data):
    result = db.execute(
        table.insert(),
        [row_data]
    )
    return result.inserted_primary_key[0]


class TestNodeGroupsMigration(base.BaseAlembicMigrationTest):

    def test_name_cluster_unique_constraint_migration(self):
        names = db.execute(
            sa.select([self.meta.tables['nodegroups'].c.name])).fetchall()
        self.assertIn(('test_nodegroup_a_0',), names)
        self.assertIn(('test_nodegroup_a_1',), names)
        self.assertIn(('test_nodegroup_b_0',), names)
        self.assertIn(('test_nodegroup_b_1',), names)

    def test_unique_name_fields_insert_duplicated(self):
        nodegroup = db.execute(
            sa.select([self.meta.tables['nodegroups'].c.cluster_id,
                       self.meta.tables['nodegroups'].c.name])).fetchone()
        with self.assertRaisesRegexp(IntegrityError,
                                     'duplicate key value violates unique '
                                     'constraint "_name_cluster_uc"'):
            insert_table_row(self.meta.tables['nodegroups'],
                             {'cluster_id': nodegroup['cluster_id'],
                              'name': nodegroup['name']})

    def test_unique_name_fields_insert_unique(self):
        nodegroup = db.execute(
            sa.select([self.meta.tables['nodegroups'].c.cluster_id,
                       self.meta.tables['nodegroups'].c.name])).fetchone()
        db.execute(self.meta.tables['nodegroups'].insert(),
                   [{'cluster_id': nodegroup['cluster_id'],
                     'name': six.text_type(uuid.uuid4())}])


class TestReleaseMigrations(base.BaseAlembicMigrationTest):

    def test_release_is_deployable_deleted(self):
        self.assertNotIn('is_deployable',
                         [c.name for c in self.meta.tables['releases'].c])

    def test_releases_are_manageonly(self):
        states = [r[0] for r in db.execute(
            sa.select([self.meta.tables['releases'].c.state])).fetchall()]

        for state in states:
            self.assertEqual(state, 'manageonly')

    def test_new_component_metadata_field_exists_and_empty(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.components_metadata]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), [])


class TestTaskStatus(base.BaseAlembicMigrationTest):

    def test_pending_status_saving(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [
                {
                    'cluster_id': None,
                    'uuid': 'fake_task_uuid_0',
                    'name': consts.TASK_NAMES.node_deletion,
                    'message': None,
                    'status': consts.TASK_STATUSES.pending,
                    'progress': 0,
                    'cache': None,
                    'result': None,
                    'parent_id': None,
                    'weight': 1
                }
            ])

        result = db.execute(
            sa.select([self.meta.tables['tasks'].c.status]))

        for row in result.fetchall():
            status = row[0]
            self.assertEqual(status, consts.TASK_STATUSES.pending)


class TestTaskNameMigration(base.BaseAlembicMigrationTest):

    def test_task_name_enum(self):
        added_task_names = ('update_dnsmasq',)
        tasks_table = self.meta.tables['tasks']
        for name in added_task_names:
            insert_table_row(tasks_table,
                             {'name': name,
                              'uuid': str(uuid.uuid4()),
                              'status': 'running'})

        with self.assertRaisesRegexp(DataError, 'invalid input value for '
                                                'enum task_name'):
            insert_table_row(tasks_table,
                             {'name': 'wrong_task_name',
                              'uuid': str(uuid.uuid4()),
                              'status': 'running'})


class TestPluginMigration(base.BaseAlembicMigrationTest):

    def test_new_component_metadata_field_exists_and_empty(self):
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.components_metadata]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), [])
