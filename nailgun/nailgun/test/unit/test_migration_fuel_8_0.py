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
from sqlalchemy.exc import DataError
from sqlalchemy.exc import IntegrityError
import uuid

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
            'fuel_version': '6.1',
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


class TestComponentTableMigration(base.BaseAlembicMigrationTest):
    def test_table_fields_and_default_values(self):
        component_table = self.meta.tables['components']
        insert_table_row(component_table,
                         {'name': 'test_component', 'type': 'network'})
        columns = [t.name for t in component_table.columns]
        self.assertItemsEqual(columns, ['id', 'name', 'type', 'hypervisors',
                                        'networks', 'storages',
                                        'plugin_id', 'additional_services'])

        column_with_default_values = [
            (component_table.c.hypervisors, []),
            (component_table.c.networks, []),
            (component_table.c.storages, []),
            (component_table.c.additional_services, [])
        ]
        result = db.execute(
            sa.select([item[0] for item in column_with_default_values]))
        db_values = result.fetchone()

        for idx, db_value in enumerate(db_values):
            self.assertEqual(db_value, column_with_default_values[idx][1])

    def test_unique_name_type_constraint(self):
        test_name = str(uuid.uuid4())
        test_type = 'storage'
        component_table = self.meta.tables['components']
        insert_table_row(component_table,
                         {'name': test_name, 'type': test_type})

        insert_table_row(component_table,
                         {'name': str(uuid.uuid4()), 'type': test_type})
        same_type_components_count = db.execute(
            sa.select([sa.func.count(component_table.c.name)]).
            where(component_table.c.type == test_type)
        ).fetchone()[0]
        self.assertEqual(same_type_components_count, 2)

        with self.assertRaisesRegexp(IntegrityError,
                                     'duplicate key value violates unique '
                                     'constraint "_component_name_type_uc"'):
            insert_table_row(component_table,
                             {'name': test_name, 'type': test_type})

    def test_component_types_enum(self):
        allow_type_name = ('hypervisor', 'network', 'storage',
                           'additional_service')
        component_table = self.meta.tables['components']
        for type in allow_type_name:
            name = str(uuid.uuid4())
            insert_table_row(component_table, {'name': name, 'type': type})
            inserted_count = db.execute(
                sa.select([sa.func.count(component_table.c.name)]).
                where(sa.and_(component_table.c.type == type,
                              component_table.c.name == name))
            ).fetchone()[0]
            self.assertEqual(inserted_count, 1)

        with self.assertRaisesRegexp(DataError, 'invalid input value for '
                                                'enum component_types'):
            insert_table_row(component_table,
                             {'name': 'test', 'type': 'wrong_type_name'})

    def test_cascade_plugin_deletion(self):
        plugin_table = self.meta.tables['plugins']
        plugin_id = insert_table_row(
            plugin_table,
            {
                'name': 'test_plugin',
                'title': 'Test plugin',
                'version': '1.0.0',
                'description': 'Test plugin for Fuel',
                'homepage': 'http://fuel_plugins.test_plugin.com',
                'package_version': '3.0.0'
            }
        )
        component_table = self.meta.tables['components']
        insert_table_row(
            component_table,
            {'name': 'test_name', 'plugin_id': plugin_id, 'type': 'storage'})
        db.execute(
            sa.delete(plugin_table).where(plugin_table.c.id == plugin_id))
        deleted_plugin_components = db.execute(
            sa.select([sa.func.count(component_table.c.name)]).
            where(component_table.c.plugin_id == plugin_id)
        ).fetchone()[0]
        self.assertEqual(deleted_plugin_components, 0)


class TestReleaseComponentTableMigration(base.BaseAlembicMigrationTest):
    def test_component_foreign_key_constraints(self):
        release_component_table = self.meta.tables['release_components']
        component_id = insert_table_row(
            self.meta.tables['components'],
            {'name': 'test_name', 'type': 'network'}
        )
        with self.assertRaisesRegexp(IntegrityError,
                                     'violates foreign key constraint '
                                     '"release_components_release_id_fkey"'):
            insert_table_row(
                release_component_table,
                {'release_id': -1, 'component_id': component_id}
            )

    def test_release_foreign_key_constraints(self):
        release_component_table = self.meta.tables['release_components']
        release_table = self.meta.tables['releases']
        release_id = db.execute(sa.select([release_table.c.id])).fetchone()[0]

        with self.assertRaisesRegexp(IntegrityError,
                                     'violates foreign key constraint '
                                     '"release_components_component_id_fkey"'):
            insert_table_row(
                release_component_table,
                {'release_id': release_id, 'component_id': -1}
            )

    def test_non_null_fields(self):
        release_component_table = self.meta.tables['release_components']
        with self.assertRaisesRegexp(IntegrityError,
                                     'violates not-null constraint'):
            insert_table_row(release_component_table, {})

    def test_cascade_release_deletion(self):
        release_component_table = self.meta.tables['release_components']
        release_table = self.meta.tables['releases']
        release_id = insert_table_row(
            release_table,
            {
                'name': 'release_with_components',
                'version': '2014.2.2-6.1',
                'operating_system': 'ubuntu',
                'state': 'available'
            }
        )
        component_id = insert_table_row(
            self.meta.tables['components'],
            {'name': str(uuid.uuid4()), 'type': 'hypervisor'}
        )
        insert_table_row(
            release_component_table,
            {'release_id': release_id, 'component_id': component_id}
        )
        db.execute(
            sa.delete(release_table).where(release_table.c.id == release_id))
        deleted_plugin_components = db.execute(
            sa.select([sa.func.count(release_component_table.c.id)]).
            where(release_component_table.c.release_id == release_id)
        ).fetchone()[0]
        self.assertEqual(deleted_plugin_components, 0)


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
        insert_table_row(self.meta.tables['nodegroups'],
                         {'cluster_id': nodegroup['cluster_id'],
                          'name': uuid.uuid4()})


class TestTaskNameMigration(base.BaseAlembicMigrationTest):

    def test_task_name_enum(self):
        added_task_names = ('update_dnsmasq',)
        tasks_table = self.meta.tables['tasks']
        for name in added_task_names:
            insert_table_row(tasks_table,
                             {'name': name,
                              'uuid': str(uuid.uuid4()),
                              'status': 'running'})
            inserted_count = db.execute(
                sa.select([sa.func.count(tasks_table.c.name)]).
                where(sa.and_(tasks_table.c.name == name))
            ).fetchone()[0]
            self.assertEqual(inserted_count, 1)

        with self.assertRaisesRegexp(DataError, 'invalid input value for '
                                                'enum task_name'):
            insert_table_row(tasks_table,
                             {'name': 'wrong_task_name',
                              'uuid': str(uuid.uuid4()),
                              'status': 'running'})
