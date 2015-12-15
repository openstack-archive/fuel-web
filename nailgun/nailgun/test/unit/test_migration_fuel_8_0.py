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
from datetime import datetime
from oslo_serialization import jsonutils
import six
import sqlalchemy as sa
from sqlalchemy.exc import DataError
from sqlalchemy.exc import IntegrityError

from nailgun import consts
from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


_prepare_revision = '1e50a4903910'
_test_revision = '43b2cb64dae6'


master_node_settings_before_migration = None


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    global master_node_settings_before_migration
    master_node_settings_before_migration = jsonutils.loads(
        get_master_node_settings())
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def get_master_node_settings():
    meta = base.reflect_db_metadata()
    master_node_settings_table = meta.tables['master_node_settings']

    settings = db.execute(sa.select(
        [master_node_settings_table.c.settings])).scalar()
    db().commit()
    return settings


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

    result = db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_a',
            'title': 'Test plugin A',
            'version': '1.0.0',
            'description': 'Test plugin A for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '3.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['6.1', '7.0']),
        }]
    )
    pluginid_a = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_b',
            'title': 'Test plugin B',
            'version': '1.0.0',
            'description': 'Test plugin B for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '3.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['6.1', '7.0']),
        }]
    )
    pluginid_b = result.inserted_primary_key[0]

    db.execute(
        meta.tables['cluster_plugins'].insert(),
        [
            {
                'cluster_id': clusterid,
                'plugin_id': pluginid_a
            },
            {
                'cluster_id': clusterid,
                'plugin_id': pluginid_b
            }
        ]
    )

    db.execute(
        meta.tables['attributes'].insert(),
        [{
            'cluster_id': clusterid,
            'editable': jsonutils.dumps({
                'test_plugin_a': {
                    'metadata': {
                        'plugin_id': pluginid_a,
                        'enabled': True,
                        'toggleable': True,
                        'weight': 70,
                    },
                    'attribute': {
                        'value': 'value',
                        'type': 'text',
                        'description': 'description',
                        'weight': 25,
                        'label': 'label'
                    }
                },
                'test_plugin_b': {
                    'metadata': {
                        'plugin_id': pluginid_b,
                        'enabled': False,
                        'toggleable': True,
                        'weight': 80,
                    }
                }
            }),
            'generated': jsonutils.dumps({}),
        }])

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


class TestNodeErrorTypeMigration(base.BaseAlembicMigrationTest):

    def test_node_error_type_enum(self):
        added_error_types = ('discover',)
        nodes_table = self.meta.tables['nodes']
        for error_type in added_error_types:
            insert_table_row(nodes_table,
                             {'name': 'node1',
                              'status': 'error',
                              'error_type': error_type,
                              'uuid': str(uuid.uuid4()),
                              'mac': '00:00:00:00:00:00',
                              'timestamp': datetime.now()})
            inserted_count = db.execute(
                sa.select([sa.func.count(nodes_table.c.error_type)]).
                where(sa.and_(nodes_table.c.error_type == error_type))
            ).fetchone()[0]
            self.assertEqual(inserted_count, 1)

        with self.assertRaisesRegexp(DataError, 'invalid input value for '
                                                'enum node_error_type'):
            insert_table_row(nodes_table,
                             {'name': 'node1',
                              'status': 'error',
                              'error_type': 'wrong_error_type',
                              'uuid': str(uuid.uuid4()),
                              'mac': '00:00:00:00:00:00',
                              'timestamp': datetime.now()})


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


class TestClusterPluginsMigration(base.BaseAlembicMigrationTest):

    def _get_enabled(self, plugin_name):
        plugins = self.meta.tables['plugins']
        cluster_plugins = self.meta.tables['cluster_plugins']

        query = sa.select([cluster_plugins.c.enabled])\
            .select_from(
                sa.join(
                    cluster_plugins, plugins,
                    cluster_plugins.c.plugin_id == plugins.c.id))\
            .where(plugins.c.name == plugin_name)
        return db.execute(query).fetchone()[0]

    def test_plugin_a_is_enabled(self):
        enabled = self._get_enabled('test_plugin_a')
        self.assertTrue(enabled)

    def test_plugin_b_is_disabled(self):
        enabled = self._get_enabled('test_plugin_b')
        self.assertFalse(enabled)

    def test_moving_plugin_attributes(self):
        clusters = self.meta.tables['clusters']
        attributes = self.meta.tables['attributes']
        plugins = self.meta.tables['plugins']
        cluster_plugins = self.meta.tables['cluster_plugins']

        query = sa.select([attributes.c.editable])\
            .select_from(
                sa.join(
                    attributes, clusters,
                    attributes.c.cluster_id == clusters.c.id))
        result = jsonutils.loads(db.execute(query).fetchone()[0])
        self.assertItemsEqual(result, {})

        query = sa.select([cluster_plugins.c.attributes])\
            .select_from(
                sa.join(
                    cluster_plugins, plugins,
                    cluster_plugins.c.plugin_id == plugins.c.id))\
            .where(plugins.c.name == 'test_plugin_a')
        result = jsonutils.loads(db.execute(query).fetchone()[0])
        self.assertNotIn('metadata', result)
        self.assertItemsEqual(result['attribute'], {
            'value': 'value',
            'type': 'text',
            'description': 'description',
            'weight': 25,
            'label': 'label'
        })


class TestBaremetalFields(base.BaseAlembicMigrationTest):

    def test_baremetal_fields_saving(self):
        baremetal_gateway = '192.168.3.51'
        baremetal_range = jsonutils.dumps(['192.168.3.52', '192.168.3.254'])
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
                'internal_name': 'my_internal_name',
                'floating_name': 'my_floating_name',
                'baremetal_gateway': baremetal_gateway,
                'baremetal_range': baremetal_range,
                'segmentation_type': 'vlan',
                'net_l23_provider': 'ovs'
            }])
        result = db.execute(
            sa.select(
                [self.meta.tables['neutron_config'].c.baremetal_gateway,
                 self.meta.tables['neutron_config'].c.baremetal_range])).\
            fetchall()
        self.assertIn((baremetal_gateway, baremetal_range), result)


class TestComponentsMigration(base.BaseAlembicMigrationTest):

    def test_new_component_metadata_field_exists_and_empty(self):
        column_values = [
            (self.meta.tables['plugins'].c.components_metadata, []),
            (self.meta.tables['releases'].c.components_metadata, []),
            (self.meta.tables['clusters'].c.components, [])
        ]

        result = db.execute(sa.select(
            [item[0] for item in column_values]))
        db_values = result.fetchone()

        for idx, db_value in enumerate(db_values):
            self.assertEqual(jsonutils.loads(db_value), column_values[idx][1])

    def test_hotplug_field_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.is_hotpluggable])
        )
        self.assertTrue(all(x[0] is None for x in result))


class TestMasterNodeSettingsMigration(base.BaseAlembicMigrationTest):

    def test_bootstrap_field_exists_and_filled(self):
        settings = get_master_node_settings()
        bootstrap_settings = {
            "error": {
                "type": "hidden",
                "value": "",
                "weight": 10
            }
        }
        self.assertEqual(
            bootstrap_settings,
            settings['bootstrap']
        )

    def test_ui_settings_field_exists_and_has_default_value(self):
        settings = get_master_node_settings()
        ui_settings = settings['ui_settings']
        self.assertItemsEqual(ui_settings['view_mode'], 'standard')
        self.assertItemsEqual(ui_settings['filter'], {})
        self.assertItemsEqual(ui_settings['sort'], [{'status': 'asc'}])
        self.assertItemsEqual(ui_settings['filter_by_labels'], {})
        self.assertItemsEqual(ui_settings['sort_by_labels'], [])
        self.assertItemsEqual(ui_settings['search'], '')

    def test_master_node_settings_old_data_not_modified(self):
        settings = get_master_node_settings()
        settings.pop('bootstrap')
        settings.pop('ui_settings')
        self.assertDictEqual(
            master_node_settings_before_migration,
            settings
        )


class TestClusterPluginLinks(base.BaseAlembicMigrationTest):
    def test_cluster_plugin_links_creation(self):
        clusters = self.meta.tables['clusters']
        cluster_plugin_links = self.meta.tables['cluster_plugin_links']

        cluster_id = db.execute(sa.select([clusters])).scalar()

        db.execute(
            cluster_plugin_links.insert(),
            [{
                'cluster_id': cluster_id,
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description',
                'hidden': False
            }])


class TestOpenstackConfigMigration(base.BaseAlembicMigrationTest):

    def test_openstack_configs_table_saving(self):
        result = db.execute(
            sa.select([self.meta.tables['clusters'].c.id]))
        cluster_id = result.fetchone()[0]

        db.execute(
            self.meta.tables['openstack_configs'].insert(),
            [{
                'cluster_id': cluster_id,
                'is_active': True,
                'config_type': 'cluster',
                'node_id': None,
                'node_role': None,
                'created_at': datetime.now(),
                'configuration': jsonutils.dumps({
                    'config_a': {},
                    'config_b': {},
                }),
            }]
        )

        result = db.execute(
            sa.select([self.meta.tables['openstack_configs'].c.cluster_id]))
        config = result.fetchone()
        self.assertEqual(config[0], cluster_id)


class TestPluginLinks(base.BaseAlembicMigrationTest):
    def test_plugin_links_creation(self):
        plugins = self.meta.tables['plugins']
        plugin_links = self.meta.tables['plugin_links']
        plugin_id = db.execute(sa.select([plugins])).scalar()
        plugin_link_data = {
            'plugin_id': plugin_id,
            'title': 'title',
            'url': 'http://www.zzz.com',
            'description': 'description',
            'hidden': False
        }

        link_id = db.execute(
            plugin_links.insert(),
            [plugin_link_data]
        ).inserted_primary_key[0]
        fetched_data = db.execute(sa.select([plugin_links])).fetchone()
        self.assertEqual(link_id, fetched_data[0])


class TestOswlStats(base.BaseAlembicMigrationTest):
    def test_oswl_stats_creation(self):
        oswl = self.meta.tables['oswl_stats']
        expected_version_info = {"fuel_release": "7.0"}
        oswl_data = {
            'cluster_id': 0,
            'created_date': datetime.utcnow().date(),
            'updated_time': datetime.utcnow().time(),
            'resource_type': 'vm',
            'resource_checksum': 'x',
            'is_sent': False,
            'version_info': expected_version_info
        }

        expected_id = db.execute(
            oswl.insert(), [oswl_data]).inserted_primary_key[0]
        actual_id, actual_version_info = db.execute(
            sa.select([oswl.c.id, oswl.c.version_info])
        ).first()
        self.assertEqual(expected_id, actual_id)
        self.assertEqual(expected_version_info, actual_version_info)
