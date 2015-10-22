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

import uuid

import alembic
from oslo_serialization import jsonutils
import sqlalchemy as sa
from sqlalchemy.exc import DataError
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
            'state': 'available',
            'networks_metadata': jsonutils.dumps({
                'neutron': {
                    'networks': [],
                    'config': {}
                }
            })
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

    netconfigid = insert_table_row(
        meta.tables['networking_configs'],
        {
            'cluster_id': None,
            'dns_nameservers': ['8.8.8.8'],
            'floating_ranges': [],
            'configuration_template': None,
        })

    db.execute(
        meta.tables['neutron_config'].insert(),
        [{
            'id': netconfigid,
            'vlan_range': [],
            'gre_id_range': [],
            'base_mac': '00:00:00:00:00:00',
            'internal_cidr': '10.10.10.00/24',
            'internal_gateway': '10.10.10.01',
            'segmentation_type': 'vlan',
            'net_l23_provider': 'ovs'
        }])

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


class TestNeutronConfigInternalFloatingNames(base.BaseAlembicMigrationTest):

    def test_internal_name_and_floating_names_are_added(self):
        columns = [t.name for t in self.meta.tables['neutron_config'].columns]

        self.assertIn('internal_name', columns)
        self.assertIn('floating_name', columns)

    def test_internal_name_and_floating_names_defaults(self):
        result = db.execute(
            sa.select([
                self.meta.tables['neutron_config'].c.internal_name,
                self.meta.tables['neutron_config'].c.floating_name]))

        for internal_name, floating_name in result:
            self.assertEqual('net04', internal_name)
            self.assertEqual('net04_ext', floating_name)

    def test_neutron_config_is_updated_in_releases(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.networks_metadata]))

        for networks_metadata, in result:
            networks_metadata = jsonutils.loads(networks_metadata)
            neutron_config = networks_metadata['neutron']['config']

            self.assertEqual('net04', neutron_config['internal_name'])
            self.assertEqual('net04_ext', neutron_config['floating_name'])
