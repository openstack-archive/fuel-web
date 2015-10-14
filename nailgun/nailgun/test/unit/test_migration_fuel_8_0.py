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
from sqlalchemy.exc import IntegrityError

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


_prepare_revision = '1e50a4903910'
_test_revision = '43b2cb64dae6'


def setup_module(module):
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)
    post_migration_prepare()


def post_migration_prepare():
    meta = base.reflect_db_metadata()
    create_component(meta, {'name': 'test_component'})
    db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin',
            'title': 'Test plugin',
            'version': '1.0.0',
            'description': 'Test plugin for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '3.0.0'
        }])

    db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2014.2.2-6.1',
            'operating_system': 'ubuntu',
            'state': 'available'
        }])

    db.commit()


def create_component(meta, data):
    result = db.execute(
        meta.tables['components'].insert(),
        [data]
    )
    return result


class TestComponentTableMigration(base.BaseAlembicMigrationTest):
    def test_table_fields_and_default_values(self):
        component_table = self.meta.tables['components']
        columns = [t.name for t in component_table.columns]
        self.assertItemsEqual(columns, ['id', 'name', 'hypervisors',
                                        'networks', 'storages', 'release_id',
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

    def test_unique_name_fields(self):
        component_table = self.meta.tables['components']
        component_name = db.execute(
            sa.select([component_table.c.name])).fetchone()[0]
        with self.assertRaisesRegexp(IntegrityError,
                                     'duplicate key value violates unique '
                                     'constraint "components_name_key"'):
            create_component(self.meta, {'name': component_name})

    def test_cascade_plugin_deletion(self):
        plugin_table = self.meta.tables['plugins']
        plugin_id = db.execute(sa.select([plugin_table.c.id])).fetchone()[0]
        component_table = self.meta.tables['components']
        create_component(self.meta,
                         {'name': 'test_name', 'plugin_id': plugin_id})
        db.execute(
            sa.delete(plugin_table).where(plugin_table.c.id == plugin_id))
        deleted_plugin_components = db.execute(
            sa.select([component_table.c.name]).
            where(component_table.c.plugin_id == plugin_id)
        )
        self.assertEqual(deleted_plugin_components.rowcount, 0)

    def test_cascade_release_deletion(self):
        release_table = self.meta.tables['releases']
        release_id = db.execute(sa.select([release_table.c.id])).fetchone()[0]
        component_table = self.meta.tables['components']
        create_component(self.meta,
                         {'name': 'test_name', 'release_id': release_id})
        db.execute(
            sa.delete(release_table).where(release_table.c.id == release_id))
        deleted_release_components = db.execute(
            sa.select([component_table.c.name]).
            where(component_table.c.release_id == release_id)
        )
        self.assertEqual(deleted_release_components.rowcount, 0)
