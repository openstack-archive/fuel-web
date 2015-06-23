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

import datetime

import alembic
from oslo.serialization import jsonutils
import six
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.extensions.consts import extensions_migration_buffer_table_name
from nailgun.test import base


_prepare_revision = '37608259013'
_test_revision = '1e50a4903910'


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
            'fuel_version': jsonutils.dumps(['6.1', '7.0']),
        }])

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2014.2-6.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'roles': jsonutils.dumps([
                'controller',
                'compute',
                'mongo',
            ]),
            'roles_metadata': jsonutils.dumps({
                'controller': {
                    'name': 'Controller',
                    'description': 'Controller role',
                    'has_primary': True,
                },
                'zabbix-server': {
                    'name': 'Zabbix Server',
                    'description': 'Zabbix Server role'
                },
                'cinder': {
                    'name': 'Cinder',
                    'description': 'Cinder role'
                },
                'mongo': {
                    'name': 'Telemetry - MongoDB',
                    'description': 'mongo is',
                    'has_primary': True,
                }
            }),
            'attributes_metadata': jsonutils.dumps({}),
            'networks_metadata': jsonutils.dumps({}),
            'is_deployable': True,
        }])
    releaseid = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['nodes'].insert(),
        [
            {
                'uuid': 'one',
                'cluster_id': None,
                'group_id': None,
                'status': 'ready',
                'meta': '{}',
                'mac': 'aa:aa:aa:aa:aa:aa',
                'pending_addition': True,
                'pending_deletion': False,
                'timestamp': datetime.datetime.utcnow(),
            }
        ])
    nodeid_a = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['nodes'].insert(),
        [
            {
                'uuid': 'two',
                'cluster_id': None,
                'group_id': None,
                'status': 'discover',
                'meta': '{}',
                'mac': 'bb:bb:bb:bb:bb:bb',
                'pending_addition': True,
                'pending_deletion': False,
                'timestamp': datetime.datetime.utcnow(),
            }
        ])
    nodeid_b = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['nodes'].insert(),
        [
            {
                'uuid': 'three',
                'cluster_id': None,
                'group_id': None,
                'status': 'discover',
                'meta': '{}',
                'mac': 'cc:cc:cc:cc:cc:cc',
                'pending_addition': True,
                'pending_deletion': False,
                'timestamp': datetime.datetime.utcnow(),
            }
        ])
    nodeid_c = result.inserted_primary_key[0]

    db.execute(
        meta.tables['node_attributes'].insert(),
        [
            {
                'node_id': nodeid_a,
                'volumes': jsonutils.dumps([{'volume': nodeid_a}])
            },
            {
                'node_id': nodeid_b,
                'volumes': jsonutils.dumps([{'volume': nodeid_b}])
            },
            {
                'node_id': nodeid_c,
                'volumes': jsonutils.dumps([{'volume': nodeid_c}])
            },
        ])

    result = db.execute(
        meta.tables['roles'].insert(),
        [
            {'release_id': releaseid, 'name': 'controller'},
        ])
    controllerroleid = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['roles'].insert(),
        [
            {'release_id': releaseid, 'name': 'mongo'},
        ])
    mongoroleid = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['node_roles'].insert(),
        [
            {'role': controllerroleid, 'node': nodeid_a, 'primary': False},
            {'role': controllerroleid, 'node': nodeid_b, 'primary': False},
            {'role': controllerroleid, 'node': nodeid_c, 'primary': True},
            {'role': mongoroleid, 'node': nodeid_a, 'primary': False},
        ])

    result = db.execute(
        meta.tables['pending_node_roles'].insert(),
        [
            {'role': mongoroleid, 'node': nodeid_b, 'primary': True},
            {'role': mongoroleid, 'node': nodeid_c, 'primary': False},
        ])

    db.execute(
        meta.tables['node_bond_interfaces'].insert(),
        [{
            'node_id': nodeid_a,
            'name': 'test_bond_interface',
            'mode': 'active-backup',
            'bond_properties': jsonutils.dumps(
                {'test_property': 'test_value'})
        }])

    db.execute(
        meta.tables['node_nic_interfaces'].insert(),
        [{
            'node_id': nodeid_a,
            'name': 'test_interface',
            'mac': '00:00:00:00:00:01',
            'max_speed': 200,
            'current_speed': 100,
            'ip_addr': '10.20.0.2',
            'netmask': '255.255.255.0',
            'state': 'test_state',
            'interface_properties': jsonutils.dumps(
                {'test_property': 'test_value'}),
            'parent_id': 1,
            'driver': 'test_driver',
            'bus_info': 'some_test_info'
        }])

    db.commit()


class TestPluginAttributesMigration(base.BaseAlembicMigrationTest):

    def test_old_fields_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.name]))
        self.assertEqual(
            result.fetchone()[0], 'test_plugin')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.title]))
        self.assertEqual(
            result.fetchone()[0], 'Test plugin')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.version]))
        self.assertEqual(
            result.fetchone()[0], '1.0.0')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.description]))
        self.assertEqual(
            result.fetchone()[0], 'Test plugin for Fuel')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.homepage]))
        self.assertEqual(
            result.fetchone()[0], 'http://fuel_plugins.test_plugin.com')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.package_version]))
        self.assertEqual(
            result.fetchone()[0], '3.0.0')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.groups]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), ['tgroup'])

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.authors]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), ['tauthor'])

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.licenses]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), ['tlicense'])

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.releases]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]),
            [{'repository_path': 'repositories/ubuntu'}])

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.fuel_version]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), ['6.1', '7.0'])

    def test_new_fields_exists_and_empty(self):
        # check attributes_metadata field exists
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.attributes_metadata]))
        # check attributes_metadata value is empty
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), {})

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.volumes_metadata]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), {})

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.roles_metadata]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), {})

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.deployment_tasks]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), [])

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.tasks]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), [])


class TestPublicIpRequired(base.BaseAlembicMigrationTest):

    def test_public_ip_required(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.roles_metadata]))
        roles_metadata = jsonutils.loads(result.fetchone()[0])
        for role, role_info in six.iteritems(roles_metadata):
            if role in ['controller', 'zabbix-server']:
                self.assertTrue(role_info['public_ip_required'])
            else:
                self.assertFalse(role_info.get('public_ip_required'))


class TestInterfacesOffloadingModesMigration(base.BaseAlembicMigrationTest):
    def test_old_fields_exists(self):
        # check node_nic_interfaces fields
        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces'].c.node_id]))
        self.assertEqual(
            result.fetchone()[0], 1)

        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces'].c.name]))
        self.assertEqual(
            result.fetchone()[0], 'test_interface')

        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces'].c.mac]))
        self.assertEqual(
            result.fetchone()[0], '00:00:00:00:00:01')

        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces'].c.max_speed]))
        self.assertEqual(
            result.fetchone()[0], 200)

        result = db.execute(
            sa.select(
                [self.meta.tables['node_nic_interfaces'].c.current_speed]))
        self.assertEqual(
            result.fetchone()[0], 100)

        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces'].c.ip_addr]))
        self.assertEqual(
            result.fetchone()[0], '10.20.0.2')

        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces'].c.netmask]))
        self.assertEqual(
            result.fetchone()[0], '255.255.255.0')

        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces'].c.state]))
        self.assertEqual(
            result.fetchone()[0], 'test_state')

        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces']
                       .c.interface_properties]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]),
            {'test_property': 'test_value'})

        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces'].c.parent_id]))
        self.assertEqual(
            result.fetchone()[0], 1)

        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces'].c.driver]))
        self.assertEqual(
            result.fetchone()[0], 'test_driver')

        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces'].c.bus_info]))
        self.assertEqual(
            result.fetchone()[0], 'some_test_info')

    def test_new_fields_exists_and_empty(self):
        # check node_nic_interfaces fields
        result = db.execute(
            sa.select([self.meta.tables['node_nic_interfaces']
                      .c.offloading_modes]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), [])
        # the same for bond interfaces
        result = db.execute(
            sa.select([self.meta.tables['node_bond_interfaces']
                      .c.offloading_modes]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), [])


class TestMigrateVolumesIntoExtension(base.BaseAlembicMigrationTest):

    def test_data_are_moved_into_buffer_table(self):
        # "volumes" column got deleted
        columns = [t.name for t in self.meta.tables['node_attributes'].columns]
        self.assertItemsEqual(columns, ['id', 'node_id', 'interfaces',
                                        'vms_conf'])

        # The data are stored in the buffer
        table_name = extensions_migration_buffer_table_name
        result = db.execute(
            sa.select([
                self.meta.tables[table_name].c.id,
                self.meta.tables[table_name].c.extension_name,
                self.meta.tables[table_name].c.data]))
        records = list(result)

        # Extension name is volume_manager
        names = [r[1] for r in records]
        self.assertEqual(
            list(names),
            ['volume_manager'] * 3)

        # Check the data, each dict has node_id and volumes
        volumes = [jsonutils.loads(r[2]) for r in records]
        for volume in volumes:
            self.assertEqual(
                volume['volumes'],
                [{'volume': volume['node_id']}])


class TestSchemalessRoles(base.BaseAlembicMigrationTest):

    def test_nodes_has_roles_attrs(self):
        result = db.execute(
            sa.select([
                self.meta.tables['nodes'].c.roles,
                self.meta.tables['nodes'].c.pending_roles,
                self.meta.tables['nodes'].c.primary_roles,
            ]).order_by(self.meta.tables['nodes'].c.id))

        nodes = [
            (roles, pending_roles, primary_roles)
            for roles, pending_roles, primary_roles in result
        ]

        # node_a
        roles, pending_roles, primary_roles = nodes[0]

        self.assertItemsEqual(['controller', 'mongo'], roles)
        self.assertItemsEqual([], pending_roles)
        self.assertItemsEqual([], primary_roles)

        # node_b
        roles, pending_roles, primary_roles = nodes[1]

        self.assertItemsEqual(['controller'], roles)
        self.assertItemsEqual(['mongo'], pending_roles)
        self.assertItemsEqual(['mongo'], primary_roles)

        # node_c
        roles, pending_roles, primary_roles = nodes[2]

        self.assertItemsEqual(['controller'], roles)
        self.assertItemsEqual(['mongo'], pending_roles)
        self.assertItemsEqual(['controller'], primary_roles)

    def test_old_tables_are_dropped(self):
        self.assertNotIn('node_roles', self.meta.tables)
        self.assertNotIn('pending_node_roles', self.meta.tables)
        self.assertNotIn('roles', self.meta.tables)
