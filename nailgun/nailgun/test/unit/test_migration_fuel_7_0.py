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

_RELEASE = {
    'name': 'test_name',
    'version': '2015.2-7.0',
    'operating_system': 'ubuntu',
    'state': 'available',
    'roles_metadata': jsonutils.dumps({
        "controller": {
            "name": "Controller",
            "description": "Controller role"
        },
        "zabbix-server": {
            "name": "Zabbix Server",
            "description": "Zabbix Server role"
        },
        "cinder": {
            "name": "Cinder",
            "description": "Cinder role"
        }
    }),
    'attributes_metadata': jsonutils.dumps({
        'editable': {
            'storage': {
                'volumes_lvm': {},
            },
            'common': {},
        },
        'generated': {
            'cobbler': {'profile': {
                'generator_arg': 'ubuntu_1204_x86_64'}}},
    }),
    'networks_metadata': jsonutils.dumps({
        'neutron': {
            'networks': [
                {
                    'assign_vip': True,
                },
            ]
        }

    }),
    'is_deployable': True
}


def setup_module(module):
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare_nodes_with_attributes(meta):
    for i in range(2):
        db.execute(
            meta.tables['nodes'].insert(),
            [{'uuid': 'uuid{0}'.format(i),
              'status': 'ready',
              'mac': 'mac:{0}'.format(i),
              'timestamp': '12-12-2015'}])

    ids = [i[0] for i in db.execute(
        sa.select([meta.tables['nodes'].c.id]))]

    for idx in ids:
        db.execute(
            meta.tables['node_attributes'].insert(),
            [{'node_id': idx,
              'volumes': jsonutils.dumps([{'volume': idx}])}])

    return ids


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

    db.execute(meta.tables['releases'].insert(), [_RELEASE])

    node_ids = prepare_nodes_with_attributes(meta)

    db.execute(
        meta.tables['node_nic_interfaces'].insert(),
        [
            {
                'id': 1,
                'node_id': node_ids[0],
                'name': 'test_interface',
                'mac': '00:00:00:00:00:01',
                'max_speed': 200,
                'current_speed': 100,
                'ip_addr': '10.20.0.2',
                'netmask': '255.255.255.0',
                'state': 'test_state',
                'interface_properties': jsonutils.dumps(
                    {'test_property': 'test_value'}),
                'driver': 'test_driver',
                'bus_info': 'some_test_info'
            },
            {
                'id': 2,
                'node_id': node_ids[0],
                'name': 'test_interface_2',
                'mac': '00:00:00:00:00:02',
                'max_speed': 200,
                'current_speed': 100,
                'ip_addr': '10.30.0.2',
                'netmask': '255.255.255.0',
                'state': 'test_state',
                'interface_properties': jsonutils.dumps(
                    {'test_property': 'test_value'}),
                'driver': 'test_driver',
                'bus_info': 'some_test_info'
            },
            {
                'id': 3,
                'node_id': node_ids[0],
                'name': 'test_interface_3',
                'mac': '00:00:00:00:00:03',
                'max_speed': 200,
                'current_speed': 100,
                'ip_addr': '10.30.0.2',
                'netmask': '255.255.255.0',
                'state': 'test_state',
                'interface_properties': jsonutils.dumps(
                    {'test_property': 'test_value'}),
                'driver': 'test_driver',
                'bus_info': 'some_test_info'
            }])

    db.execute(
        meta.tables['node_bond_interfaces'].insert(),
        [{
            'node_id': node_ids[0],
            'name': 'test_bond_interface',
            'mode': 'active-backup',
            'bond_properties': jsonutils.dumps(
                {'test_property': 'test_value'})
        }])

    db.execute(
        meta.tables['network_groups'].insert(),
        [
            {
                'id': 1,
                'name': 'fuelweb_admin',
                'vlan_start': None,
                'cidr': '10.20.0.0/24',
                'gateway': '10.20.0.200',
            },
            {
                'id': 2,
                'name': 'public',
                'vlan_start': None,
                'cidr': '10.30.0.0/24',
                'gateway': '10.30.0.200'
            }
        ]
    )

    db.execute(
        meta.tables['net_nic_assignments'].insert(),
        [
            {
                'network_id': 1,
                'interface_id': 1
            },
            {
                'network_id': 2,
                'interface_id': 2
            },
            {
                'network_id': 2,
                'interface_id': 3
            }
        ]
    )

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


class TestReleaseNetworkRolesMetadataMigration(base.BaseAlembicMigrationTest):

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
        nic_table = self.meta.tables['node_nic_interfaces']
        result = db.execute(
            sa.select([nic_table.c.node_id, nic_table.c.name, nic_table.c.mac,
                       nic_table.c.max_speed, nic_table.c.current_speed,
                       nic_table.c.ip_addr, nic_table.c.netmask,
                       nic_table.c.state, nic_table.c.interface_properties,
                       nic_table.c.driver, nic_table.c.bus_info]).
            where(nic_table.c.id == 1))
        res = result.fetchone()
        check_res = [1, u'test_interface', u'00:00:00:00:00:01', 200, 100,
                     u'10.20.0.2', u'255.255.255.0', u'test_state',
                     u'{"test_property": "test_value"}',
                     u'test_driver', u'some_test_info']
        self.assertListEqual(list(res), check_res)

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


class TestInterfacesPxePropertyMigration(base.BaseAlembicMigrationTest):

    def test_old_fields_exists(self):
        # check node_nic_interfaces fields
        ng_table = self.meta.tables['network_groups']
        result = db.execute(
            sa.select([ng_table.c.name, ng_table.c.vlan_start,
                       ng_table.c.cidr, ng_table.c.gateway]).
            where(ng_table.c.id == 1))
        res = result.fetchone()
        check_res = [u'fuelweb_admin', None, u'10.20.0.0/24', u'10.20.0.200']
        self.assertListEqual(list(res), check_res)

        result = db.execute(
            sa.select([self.meta.tables['net_nic_assignments'].c.network_id]))
        self.assertEqual(
            result.fetchone()[0], 1)

    def test_new_field_exists_and_filled(self):
        nic_table = self.meta.tables['node_nic_interfaces']
        result = db.execute(
            sa.select([nic_table.c.pxe]).where(nic_table.c.id == 1))
        # check 'pxe' property is true for admin interfaces
        self.assertTrue(result.fetchone()[0])
        result = db.execute(
            sa.select([nic_table.c.pxe]).where(nic_table.c.id != 1))
        # and 'false' for any others
        for res in result.fetchall():
            self.assertFalse(res[0])


class TestMigrateVolumesIntoExtension(base.BaseAlembicMigrationTest):

    def test_data_are_moved_into_buffer_table(self):
        # "volumes" column got deleted
        columns = [t.name for t in self.meta.tables['node_attributes'].columns]
        self.assertItemsEqual(columns, ['id', 'node_id', 'interfaces'])

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
            ['volume_manager'] * 2)

        # Check the data, each dict has node_id and volumes
        volumes = [jsonutils.loads(r[2]) for r in records]
        for volume in volumes:
            self.assertEqual(
                volume['volumes'],
                [{'volume': volume['node_id']}])
