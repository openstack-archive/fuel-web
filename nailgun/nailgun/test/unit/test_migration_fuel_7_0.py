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
from oslo_serialization import jsonutils
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
            'version': '2014.2.2-6.1',
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
            'networks_metadata': jsonutils.dumps({
                'bonding': {
                    'properties': {
                        'linux': {
                            'mode': [
                                {
                                    "values": ["balance-rr",
                                               "active-backup",
                                               "802.3ad"]
                                },
                                {
                                    "values": ["balance-xor",
                                               "broadcast",
                                               "balance-tlb",
                                               "balance-alb"],
                                    "condition": "'experimental' in "
                                                 "version:feature_groups"
                                }
                            ]
                        }
                    }
                },
            }),
            'is_deployable': True,
        }])
    releaseid = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name_2',
            'version': '2014.2-6.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'roles': jsonutils.dumps([
                'controller',
                'compute',
                'mongo',
            ]),
            'roles_metadata': jsonutils.dumps({}),
            'attributes_metadata': jsonutils.dumps({}),
            'networks_metadata': jsonutils.dumps({
                'bonding': {
                    'properties': {
                        'ovs': {
                            'mode': [
                                {
                                    "values": ["active-backup",
                                               "balance-slb",
                                               "lacp-balance-tcp"]
                                }
                            ]
                        }
                    }
                },
            }),
            'is_deployable': True
        }])

    result = db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test_env',
            'release_id': releaseid,
            'mode': 'ha_compact',
            'status': 'new',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '6.1',
        }])
    clusterid = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['networking_configs'].insert(),
        [{
            'cluster_id': None,
            'dns_nameservers': ['8.8.8.8'],
            'floating_ranges': [],
            'configuration_template': None,
        }])
    db.execute(
        meta.tables['neutron_config'].insert(),
        [{
            'id': result.inserted_primary_key[0],
            'vlan_range': [],
            'gre_id_range': [],
            'base_mac': '00:00:00:00:00:00',
            'internal_cidr': '10.10.10.00/24',
            'internal_gateway': '10.10.10.01',
            'segmentation_type': 'vlan',
            'net_l23_provider': 'ovs'
        }])

    result = db.execute(
        meta.tables['nodes'].insert(),
        [
            {
                'uuid': 'one',
                'cluster_id': clusterid,
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
                'cluster_id': clusterid,
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
        meta.tables['node_nic_interfaces'].insert(),
        [
            {
                'id': 1,
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
                'driver': 'test_driver',
                'bus_info': 'some_test_info'
            },
            {
                'id': 2,
                'node_id': nodeid_a,
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
                'node_id': nodeid_a,
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
            'node_id': nodeid_a,
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
        plugin_table = self.meta.tables['plugins']
        column_values = [
            (plugin_table.c.attributes_metadata, {}),
            (plugin_table.c.volumes_metadata, {}),
            (plugin_table.c.roles_metadata, {}),
            (plugin_table.c.network_roles_metadata, []),
            (plugin_table.c.deployment_tasks, []),
            (plugin_table.c.tasks, []),
        ]
        result = db.execute(sa.select(
            [item[0] for item in column_values]))
        db_values = result.fetchone()

        for idx, db_value in enumerate(db_values):
            self.assertEqual(jsonutils.loads(db_value), column_values[idx][1])


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


class TestNetworkingTemplatesMigration(base.BaseAlembicMigrationTest):
    def test_new_fields_exists_and_empty(self):
        result = db.execute(
            sa.select([self.meta.tables['networking_configs']
                       .c.configuration_template]))
        self.assertIsNone(result.fetchone()[0])

        result = db.execute(
            sa.select([self.meta.tables['nodes']
                       .c.network_template]))
        self.assertIsNone(result.fetchone()[0])


class TestNodeHostnamePropertyMigration(base.BaseAlembicMigrationTest):

    def test_hostname_field_exists_and_contains_correct_values(self):
        result = db.execute(
            sa.select([self.meta.tables['nodes'].c.id,
                       self.meta.tables['nodes'].c.hostname]))

        for node_id, hostname in result:
            self.assertEqual(
                "node-{0}".format(node_id),
                hostname)

    def test_fqdn_field_is_dropped(self):
        node_table = self.meta.tables['nodes']
        self.assertNotIn('fqdn', node_table.c)


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

    def test_network_roles_metadata_exists_and_empty(self):
        # check attributes_metadata field exists
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.network_roles_metadata]))
        # check attributes_metadata value is empty
        self.assertEqual(jsonutils.loads(result.fetchone()[0]), [])

    def test_weight_is_injected_to_roles_meta(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.roles_metadata])
        )
        rel_row = result.fetchone()

        r_meta = jsonutils.loads(rel_row[0])

        default_roles_weight = {
            "controller": 10,
            "compute": 20,
            "cinder": 30,
            "cinder-vmware": 40,
            "ceph-osd": 50,
            "mongo": 60,
            "base-os": 70,
            "virt": 80
        }

        for r_name in r_meta:
            r_weight = r_meta[r_name].get('weight')
            self.assertIsNotNone(r_weight)

            if r_name in default_roles_weight:
                self.assertEquals(
                    r_weight, default_roles_weight.get(r_name)
                )
            # role which is not present in list of default ones
            else:
                self.assertEquals(r_weight, 10000)


class TestClusterUISettingsMigration(base.BaseAlembicMigrationTest):
    def test_grouping_field_removed(self):
        clusters_table = self.meta.tables['clusters']
        self.assertNotIn('grouping', clusters_table.c)

    def test_ui_settings_field_exists_and_has_default_value(self):
        clusters_table = self.meta.tables['clusters']
        self.assertIn('ui_settings', clusters_table.c)

        ui_settings = jsonutils.loads(
            db.execute(
                sa.select([clusters_table.c.ui_settings])
            ).fetchone()[0]
        )
        self.assertItemsEqual(ui_settings['view_mode'], 'standard')
        self.assertItemsEqual(ui_settings['filter'], {})
        self.assertItemsEqual(ui_settings['sort'], [{'roles': 'asc'}])
        self.assertItemsEqual(ui_settings['filter_by_labels'], {})
        self.assertItemsEqual(ui_settings['sort_by_labels'], [])
        self.assertItemsEqual(ui_settings['search'], '')


class TestClusterBondMetaMigration(base.BaseAlembicMigrationTest):
    def test_cluster_bond_meta_field_exists_and_has_proper_value_lnx(self):
        lnx_meta = [
            {
                "values": ["balance-rr", "active-backup", "802.3ad"],
                "condition": "interface:pxe == false"
            },
            {
                "values": ["balance-xor", "broadcast", "balance-tlb",
                           "balance-alb"],
                "condition": "interface:pxe == false and "
                             "'experimental' in version:feature_groups"
            }
        ]
        # check data for linux bonds (fuel 6.1 version)
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.networks_metadata]).
            where(self.meta.tables['releases'].c.name == 'test_name'))
        bond_meta = jsonutils.loads(result.fetchone()[0])['bonding']
        self.assertEqual(bond_meta['properties']['linux']['mode'], lnx_meta)

    def test_cluster_bond_meta_field_exists_and_has_proper_value_ovs(self):
        ovs_meta = [
            {
                "values": ["active-backup", "balance-slb",
                           "lacp-balance-tcp"],
                "condition": "interface:pxe == false"
            }
        ]
        # check data for ovs bonds (fuel < 6.1 version)
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.networks_metadata]).
            where(self.meta.tables['releases'].c.name == 'test_name_2'))
        bond_meta = jsonutils.loads(result.fetchone()[0])['bonding']
        self.assertEqual(bond_meta['properties']['ovs']['mode'], ovs_meta)


class TestExtensionsField(base.BaseAlembicMigrationTest):

    def test_extensions_field_with_default_data(self):
        cluster_result = db.execute(
            sa.select([self.meta.tables['clusters'].c.extensions])).fetchone()
        release_result = db.execute(
            sa.select([self.meta.tables['releases'].c.extensions])).fetchone()

        self.assertEqual(list(cluster_result)[0], ['volume_manager'])
        self.assertEqual(list(release_result)[0], ['volume_manager'])


class TestOldReleasesIsUndeployable(base.BaseAlembicMigrationTest):

    def test_old_releases_has_deployable_false(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.is_deployable]).
            where(self.meta.tables['releases'].c.version == '2014.2.2-6.1'))

        for (is_deployable, ) in result:
            self.assertFalse(is_deployable)


class TestNodeLabelsMigration(base.BaseAlembicMigrationTest):
    def test_node_labels_field_exists_and_has_default_value(self):
        nodes_table = self.meta.tables['nodes']
        self.assertIn('labels', nodes_table.c)

        default_labels = jsonutils.loads(
            db.execute(
                sa.select([nodes_table.c.labels])
            ).fetchone()[0]
        )
        self.assertEqual(default_labels, {})


class TestTunSegmentType(base.BaseAlembicMigrationTest):

    def test_tun_segment_type_added(self):
        result = db.execute(
            self.meta.tables['networking_configs'].insert(),
            [{
                'cluster_id': None,
                'dns_nameservers': ['8.8.8.8'],
                'floating_ranges': [],
                'configuration_template': None,
            }])
        db.execute(
            self.meta.tables['neutron_config'].insert(),
            [{
                'id': result.inserted_primary_key[0],
                'vlan_range': [],
                'gre_id_range': [],
                'base_mac': '00:00:00:00:00:00',
                'internal_cidr': '10.10.10.00/24',
                'internal_gateway': '10.10.10.01',
                'segmentation_type': 'tun',
                'net_l23_provider': 'ovs'
            }])
        types = db.execute(
            sa.select(
                [self.meta.tables['neutron_config'].c.segmentation_type])).\
            fetchall()
        self.assertIn(('tun',), types)


class TestStringNetworkGroupName(base.BaseAlembicMigrationTest):

    def test_network_group_name_is_string(self):
        db.execute(
            self.meta.tables['network_groups'].insert(),
            [{
                'id': 3,
                'name': 'custom_name',
                'vlan_start': None,
                'cidr': '10.20.0.0/24',
                'gateway': '10.20.0.200',
            }])
        names = db.execute(
            sa.select(
                [self.meta.tables['network_groups'].c.name])). \
            fetchall()
        self.assertIn(('custom_name',), names)
