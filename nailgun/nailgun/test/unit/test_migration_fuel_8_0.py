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
    setup_component_table_tests()


def prepare():
    meta = base.reflect_db_metadata()

    release_data = [{
        'name': 'test_name',
        'version': '2014.2.2-6.1',
        'operating_system': 'ubuntu',
        'state': 'available'
    }]
    result = insert_table_rows(meta.tables['releases'], release_data)
    releaseid = result.inserted_primary_key[0]

    cluster_data = [{
        'name': 'test_env',
        'release_id': releaseid,
        'mode': 'ha_compact',
        'status': 'new',
        'net_provider': 'neutron',
        'grouping': 'roles',
        'fuel_version': '6.1',
    }]
    result = insert_table_rows(meta.tables['clusters'], cluster_data)
    clusterid = result.inserted_primary_key[0]

    nodegroups_data = [
        {'cluster_id': clusterid, 'name': 'test_nodegroup_a'},
        {'cluster_id': clusterid, 'name': 'test_nodegroup_a'},
        {'cluster_id': clusterid, 'name': 'test_nodegroup_b'},
        {'cluster_id': clusterid, 'name': 'test_nodegroup_b'},
    ]
    insert_table_rows(meta.tables['nodegroups'], nodegroups_data)

    plugin_data = [{
        'name': 'test_plugin',
        'title': 'Test plugin',
        'version': '1.0.0',
        'description': 'Test plugin for Fuel',
        'homepage': 'http://fuel_plugins.test_plugin.com',
        'package_version': '3.0.0'
    }]
    insert_table_rows(meta.tables['plugins'], plugin_data)

    db.commit()


def setup_component_table_tests():
    meta = base.reflect_db_metadata()
    insert_table_rows(meta.tables['components'],
                      [{'name': 'test_component', 'type': 'network'}])
    db.commit()


def insert_table_rows(table, data):
    result = db.execute(
        table.insert(),
        data
    )
    return result


class TestComponentTableMigration(base.BaseAlembicMigrationTest):
    def test_table_fields_and_default_values(self):
        component_table = self.meta.tables['components']
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
        component_table = self.meta.tables['components']
        db_component = db.execute(sa.select(
            [component_table.c.name, component_table.c.type])).fetchone()
        db_component_type = db_component['type']
        db_component_name = db_component['name']
        insert_table_rows(component_table, [{'name': str(uuid.uuid4()),
                                             'type': db_component_type}])
        same_type_components_count = db.execute(
            sa.select([sa.func.count(component_table.c.name)]).
            where(component_table.c.type == db_component_type)
        ).fetchone()[0]
        self.assertEqual(same_type_components_count, 2)

        with self.assertRaisesRegexp(IntegrityError,
                                     'duplicate key value violates unique '
                                     'constraint "_component_name_type_uc"'):
            insert_table_rows(component_table, [{'name': db_component_name,
                                                 'type': db_component_type}])

    def test_component_types_enum(self):
        allow_type_name = ('hypervisor', 'network', 'storage',
                           'additional_service')
        component_table = self.meta.tables['components']
        for type in allow_type_name:
            name = str(uuid.uuid4())
            insert_table_rows(component_table, [{'name': name, 'type': type}])
            inserted_count = db.execute(
                sa.select([sa.func.count(component_table.c.name)]).
                where(sa.and_(component_table.c.type == type,
                              component_table.c.name == name))
            ).fetchone()[0]
            self.assertEqual(inserted_count, 1)

        with self.assertRaisesRegexp(DataError, 'invalid input value for '
                                                'enum component_types'):
            insert_table_rows(component_table, [{'name': 'test',
                                                 'type': 'wrong_type_name'}])

    def test_cascade_plugin_deletion(self):
        plugin_table = self.meta.tables['plugins']
        plugin_id = db.execute(sa.select([plugin_table.c.id])).fetchone()[0]
        component_table = self.meta.tables['components']
        insert_table_rows(
            component_table,
            [{'name': 'test_name', 'plugin_id': plugin_id, 'type': 'storage'}])
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
        component_table = self.meta.tables['components']
        component_id = db.execute(
            sa.select([component_table.c.id])).fetchone()[0]

        with self.assertRaisesRegexp(IntegrityError,
                                     'violates foreign key constraint '
                                     '"release_components_release_id_fkey"'):
            insert_table_rows(
                release_component_table,
                [{'release_id': -1, 'component_id': component_id}]
            )
            db.rollback()

    def test_release_foreign_key_constraints(self):
        release_component_table = self.meta.tables['release_components']
        release_table = self.meta.tables['releases']
        release_id = db.execute(sa.select([release_table.c.id])).fetchone()[0]

        with self.assertRaisesRegexp(IntegrityError,
                                     'violates foreign key constraint '
                                     '"release_components_component_id_fkey"'):
            insert_table_rows(
                release_component_table,
                [{'release_id': release_id, 'component_id': -1}]
            )

    def test_non_null_fields(self):
        release_component_table = self.meta.tables['release_components']
        with self.assertRaisesRegexp(IntegrityError,
                                     'violates not-null constraint'):
            insert_table_rows(release_component_table, [{}])

    def test_cascade_release_deletion(self):
        release_component_table = self.meta.tables['release_components']
        release_data = [{
            'name': 'release_with_components',
            'version': '2014.2.2-6.1',
            'operating_system': 'ubuntu',
            'state': 'available'
        }]
        release_table = self.meta.tables['releases']
        result = insert_table_rows(release_table, release_data)
        release_id = result.inserted_primary_key[0]
        component_table = self.meta.tables['components']
        component_id = db.execute(
            sa.select([component_table.c.id])).fetchone()[0]
        insert_table_rows(
            release_component_table,
            [{'release_id': release_id, 'component_id': component_id}]
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
            db.execute(self.meta.tables['nodegroups'].insert(),
                       [{'cluster_id': nodegroup['cluster_id'],
                         'name': nodegroup['name']}])

    def test_unique_name_fields_insert_unique(self):
        nodegroup = db.execute(
            sa.select([self.meta.tables['nodegroups'].c.cluster_id,
                       self.meta.tables['nodegroups'].c.name])).fetchone()
        db.execute(self.meta.tables['nodegroups'].insert(),
                   [{'cluster_id': nodegroup['cluster_id'],
                     'name': uuid.uuid4()}])
