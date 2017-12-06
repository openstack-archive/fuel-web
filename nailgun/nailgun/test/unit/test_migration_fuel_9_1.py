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
from distutils.version import StrictVersion
from oslo_serialization import jsonutils
import sqlalchemy as sa
import sqlalchemy.exc as sa_exc

from nailgun import consts
from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '675105097a69'
_test_revision = 'f2314e5d63c9'

rule_to_pick_bootdisk = [
    {'type': 'exclude_disks_by_name',
     'regex': '^nvme',
     'description': 'NVMe drives should be skipped as accessing such drives '
                    'during the boot typically requires using UEFI which is '
                    'still not supported by fuel-agent (it always installs '
                    'BIOS variant of  grub). '
                    'grub bug (http://savannah.gnu.org/bugs/?41883)'},
    {'type': 'pick_root_disk_if_disk_name_match',
     'regex': '^md',
     'root_mount': '/',
     'description': 'If we have /root on fake raid, then /boot partition '
                    'should land on to it too. We can\'t proceed with '
                    'grub-install otherwise.'}
]


JSON_TASKS = [
    {
        'id': 'post_deployment_end',
        'type': 'stage',
        'requires': ['post_deployment_start']
    },
    {
        'id': 'primary-controller',
        'parameters': {'strategy': {'type': 'one_by_one'}},
        'required_for': ['deploy_end'],
        'requires': ['deploy_start'],
        'role': ['primary-controller'],  # legacy notation should be converted
        # to `roles`
        'type': 'group'
    },
    {
        'id': 'cross-dep-test',
        'type': 'puppet',
        'cross-depended-by': ['a', 'b'],
        'cross-depends': ['c', 'd']
    },
    {
        'id': 'custom-test',
        'type': 'puppet',
        'test_pre': {'k': 'v'},
        'test_post': {'k': 'v'}
    }
]


DEPLOYMENT_INFO = {
    102: {
        'master': {
            'attr1': 1,
            'attr2': 2
        },
        '1': {
            'attr1': 3,
            'attr2': 4
        },
        '2': {
            'attr1': 5,
            'attr2': 6
        }
    },
    103: {
        'master': {
            'attr1': 7,
            'attr2': 8
        },
        '1': {
            'attr1': 9,
            'attr2': 10
        },
        '2': {
            'attr1': 11,
            'attr2': 12
        }
    }
}


ATTRIBUTES_METADATA = {
    'editable': {
        'kernel_params': {
            'kernel': {
                'value': ("console=tty0 net.ifnames=0 biosdevname=0 "
                          "rootdelay=90 nomodeset"),
            }
        },
        'common': {
            'propagate_task_deploy': {
                'type': 'hidden'
            }
        }
    }
}


VMWARE_ATTRIBUTES_METADATA = {
    'editable': {
        'metadata': [
            {
                'name': 'availability_zones',
                'fields': []
            },
            {
                'name': 'glance',
                'fields': [
                    {
                        'name': 'ca_file',
                        'description': 'xxx',
                    }
                ]
            },
        ],
        'value': {
            'availability_zones': [{}, {}],
            'glance': {},
        }
    }
}


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
            'name': 'test_name',
            'version': '2015.1-9.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'deployment_tasks': jsonutils.dumps(JSON_TASKS),
            'roles': jsonutils.dumps([
                'controller',
                'compute',
                'virt',
                'compute-vmware',
                'ironic',
                'cinder',
                'cinder-block-device',
                'cinder-vmware',
                'ceph-osd',
                'mongo',
                'base-os',
            ]),
            'roles_metadata': jsonutils.dumps({
                'controller': {
                    'name': 'Controller',
                },
                'compute': {
                    'name': 'Compute',
                },
                'virt': {
                    'name': 'Virtual',
                },
                'compute-vmware': {
                    'name': 'Compute VMware',
                },
                'ironic': {
                    'name': 'Ironic',
                },
                'cinder': {
                    'name': 'Cinder',
                },
                'cinder-block-device': {
                    'name': 'Cinder Block Device',
                },
                'cinder-vmware': {
                    'name': 'Cinder Proxy to VMware Datastore',
                },
                'ceph-osd': {
                    'name': 'Ceph OSD',
                },
                'mongo': {
                    'name': 'Telemetry - MongoDB',
                },
                'base-os': {
                    'name': 'Operating System',
                }
            }),
            'is_deployable': True,
            'networks_metadata': jsonutils.dumps({
                'neutron': {
                    'networks': [],
                    'config': {}
                },
                'dpdk_drivers': {
                    'igb_uio': ['qwe']
                },
            }),
            'volumes_metadata': jsonutils.dumps({}),
            'attributes_metadata': jsonutils.dumps(ATTRIBUTES_METADATA),
            'vmware_attributes_metadata':
                jsonutils.dumps(VMWARE_ATTRIBUTES_METADATA)
        }])

    release_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_old',
            'version': '2015.1-8.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'deployment_tasks': jsonutils.dumps(JSON_TASKS),
            'roles': '[]',
            'roles_metadata': '{}',
            'is_deployable': True,
            'networks_metadata': '{}',
        }]
    )

    cluster_ids = []
    for cluster_name in ['test_env1', 'test_env2']:
        result = db.execute(
            meta.tables['clusters'].insert(),
            [{
                'name': cluster_name,
                'release_id': release_id,
                'mode': 'ha_compact',
                'status': 'new',
                'net_provider': 'neutron',
                'grouping': 'roles',
                'fuel_version': '9.0',
                'deployment_tasks': jsonutils.dumps(JSON_TASKS)
            }])
        cluster_ids.append(result.inserted_primary_key[0])

    result = db.execute(
        meta.tables['nodes'].insert(),
        [{
            'uuid': '26b508d0-0d76-4159-bce9-f67ec2765480',
            'cluster_id': None,
            'group_id': None,
            'status': 'discover',
            'meta': '{}',
            'mac': 'aa:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
        }]
    )
    node_id = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_a',
            'title': 'Test plugin A',
            'version': '2.0.0',
            'description': 'Test plugin A for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '5.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'deployment_tasks': jsonutils.dumps(JSON_TASKS),
            'fuel_version': jsonutils.dumps(['9.0']),
            'network_roles_metadata': jsonutils.dumps([{
                'id': 'admin/vip',
                'default_mapping': 'fuelweb_admin',
                'properties': {
                    'subnet': True,
                    'gateway': False,
                    'vip': [
                        {
                            'name': 'my-vip1',
                            'namespace': 'my-namespace1',
                        },
                        {
                            'name': 'my-vip2',
                            'namespace': 'my-namespace2',
                        }
                    ]
                }
            }])
        }]
    )
    plugin_a_id = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_b',
            'title': 'Test plugin B',
            'version': '2.0.0',
            'description': 'Test plugin B for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '5.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['9.0']),
            'network_roles_metadata': jsonutils.dumps([{
                'id': 'admin/vip',
                'default_mapping': 'fuelweb_admin',
                'properties': {
                    'subnet': True,
                    'gateway': False,
                    'vip': [
                        {
                            'name': 'my-vip3',
                            'namespace': 'my-namespace3',
                        },
                        {
                            'name': 'my-vip4',
                            'namespace': 'my-namespace4',
                        }
                    ]
                }
            }])
        }]
    )
    plugin_b_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['cluster_plugins'].insert(),
        [
            {'cluster_id': cluster_ids[0], 'plugin_id': plugin_a_id},
            {'cluster_id': cluster_ids[0], 'plugin_id': plugin_b_id}
        ]
    )

    db.execute(
        meta.tables['node_nic_interfaces'].insert(),
        [{
            'id': 1,
            'node_id': node_id,
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
        }]
    )

    db.execute(
        meta.tables['node_bond_interfaces'].insert(),
        [{
            'node_id': node_id,
            'name': 'test_bond_interface',
            'mode': 'active-backup',
            'bond_properties': jsonutils.dumps(
                {'test_property': 'test_value'})
        }]
    )

    db.execute(
        meta.tables['tasks'].insert(),
        [
            {
                'id': 55,
                'uuid': '219eaafe-01a1-4f26-8edc-b9d9b0df06b3',
                'name': 'deployment',
                'status': 'running',
                'deployment_info': jsonutils.dumps({}),
            },
        ]
    )
    db.execute(
        meta.tables['deployment_history'].insert(),
        [
            {
                'uuid': 'fake_uuid_0',
                'deployment_graph_task_name': 'fake',
                'node_id': 'fake_node_id',
                'task_id': 55,
                'status': 'pending',
                'summary': jsonutils.dumps({'fake': 'fake'}),
            }
        ]
    )

    result = db.execute(
        meta.tables['tasks'].insert(),
        [
            {
                'id': 102,
                'uuid': '219eaafe-01a1-4f26-8edc-b9d9b0df06b3',
                'name': 'deployment',
                'status': 'running',
                'deployment_info': jsonutils.dumps(DEPLOYMENT_INFO[102])
            },
            {
                'id': 103,
                'uuid': 'a45fbbcd-792c-4245-a619-f4fb2f094d38',
                'name': 'deployment',
                'status': 'running',
                'deployment_info': jsonutils.dumps(DEPLOYMENT_INFO[103])
            }
        ]
    )

    db.commit()


class TestRulesToPickBootableDisk(base.BaseAlembicMigrationTest):

    def test_release_rules_to_pick_bootable_disk_creation(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.volumes_metadata])
        ).fetchone()[0]
        volumes_metadata = jsonutils.loads(result)
        self.assertIn('rule_to_pick_boot_disk', volumes_metadata)
        self.assertEqual(
            volumes_metadata['rule_to_pick_boot_disk'],
            rule_to_pick_bootdisk
        )


class TestPluginAttributesMigration(base.BaseAlembicMigrationTest):

    def test_new_attributes_fields_exist(self):
        node_bond_interfaces_table = self.meta.tables['node_bond_interfaces']
        node_nic_interfaces_table = self.meta.tables['node_nic_interfaces']
        plugins_table = self.meta.tables['plugins']
        releases_table = self.meta.tables['releases']
        columns = [
            plugins_table.c.nic_attributes_metadata,
            plugins_table.c.bond_attributes_metadata,
            plugins_table.c.node_attributes_metadata,
            node_bond_interfaces_table.c.attributes,
            node_nic_interfaces_table.c.attributes,
            node_nic_interfaces_table.c.meta,
            releases_table.c.nic_attributes,
            releases_table.c.bond_attributes
        ]

        for column in columns:
            db_values = db.execute(sa.select([column])).fetchone()
            for db_value in db_values:
                self.assertEqual(db_value, '{}')

    def test_node_nic_interface_cluster_plugins_creation(self):
        node_nic_interface_cluster_plugins = \
            self.meta.tables['node_nic_interface_cluster_plugins']
        cluster_plugins = self.meta.tables['cluster_plugins']
        node_nic_interfaces = self.meta.tables['node_nic_interfaces']
        nodes = self.meta.tables['nodes']

        cluster_plugin_id = db.execute(sa.select([cluster_plugins])).scalar()
        interface_id = db.execute(sa.select([node_nic_interfaces])).scalar()
        node_id = db.execute(sa.select([nodes])).scalar()

        db.execute(
            node_nic_interface_cluster_plugins.insert(),
            [{
                'cluster_plugin_id': cluster_plugin_id,
                'interface_id': interface_id,
                'node_id': node_id,
                'attributes': jsonutils.dumps({'test_attr': 'test'})
            }])

    def test_node_bond_interface_cluster_plugins_creation(self):
        node_bond_interface_cluster_plugins = \
            self.meta.tables['node_bond_interface_cluster_plugins']
        cluster_plugins = self.meta.tables['cluster_plugins']
        node_bond_interfaces = self.meta.tables['node_bond_interfaces']
        nodes = self.meta.tables['nodes']

        cluster_plugin_id = db.execute(sa.select([cluster_plugins])).scalar()
        bond_id = db.execute(sa.select([node_bond_interfaces])).scalar()
        node_id = db.execute(sa.select([nodes])).scalar()

        db.execute(
            node_bond_interface_cluster_plugins.insert(),
            [{
                'cluster_plugin_id': cluster_plugin_id,
                'bond_id': bond_id,
                'node_id': node_id,
                'attributes': jsonutils.dumps({'test_attr': 'test'})
            }])

    def test_node_cluster_plugins_creation(self):
        node_cluster_plugins = self.meta.tables['node_cluster_plugins']
        cluster_plugins = self.meta.tables['cluster_plugins']
        nodes = self.meta.tables['nodes']

        cluster_plugin_id = db.execute(sa.select([cluster_plugins])).scalar()
        node_id = db.execute(sa.select([nodes])).scalar()

        db.execute(
            node_cluster_plugins.insert(),
            [{
                'cluster_plugin_id': cluster_plugin_id,
                'node_id': node_id,
                'attributes': jsonutils.dumps({'test_attr': 'test'})
            }])


class TestTasksSchemaMigration(base.BaseAlembicMigrationTest):

    def test_dry_run_field_exist(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [{
                'uuid': 'fake_task_uuid_0',
                'name': 'dump',
                'status': 'pending',
            }]
        )

        result = db.execute(sa.select([self.meta.tables['tasks']])).first()
        self.assertIn('dry_run', result)

    def test_graph_type_field_exist(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [{
                'uuid': 'fake_task_uuid_0',
                'name': 'dump',
                'status': 'pending',
            }]
        )

        result = db.execute(sa.select([self.meta.tables['tasks']])).first()
        self.assertIn('graph_type', result)


class TestNodeErrorTypeMigration(base.BaseAlembicMigrationTest):

    def test_error_type_accepts_any_string_value(self):
        nodes_table = self.meta.tables['nodes']
        node_id = db.execute(sa.select([nodes_table])).scalar()
        db.execute(
            nodes_table.update(),
            [{
                'error_type': 'custom_error_type'
            }]
        )
        result = db.execute(
            sa.select([
                nodes_table.c.error_type,
            ]).where(nodes_table.c.id == node_id)
        ).first()
        self.assertEqual('custom_error_type', result[0])


class TestDeploymentGraphsMigration(base.BaseAlembicMigrationTest):

    def test_new_columns_exist(self):
        deployment_graphs_table = self.meta.tables['deployment_graphs']
        db.execute(
            deployment_graphs_table.insert(),
            {
                'name': 'test',
                'node_filter': '$.status == ready',
                'on_success': '{"node_attributes": {"status": "new"}}',
                'on_error': '{"node_attributes": {"status": "error"}}',
                'on_stop': '{}'
            }
        )

        result = db.execute(
            sa.select([
                deployment_graphs_table.c.node_filter,
                deployment_graphs_table.c.on_success,
                deployment_graphs_table.c.on_error,
                deployment_graphs_table.c.on_stop,
            ]).where(deployment_graphs_table.c.name == 'test')
        ).first()

        self.assertEqual('$.status == ready', result['node_filter'])
        self.assertEqual(
            '{"node_attributes": {"status": "new"}}', result['on_success']
        )
        self.assertEqual(
            '{"node_attributes": {"status": "error"}}', result['on_error']
        )
        self.assertEqual('{}', result['on_stop'])


class TestOrchestratorTaskTypesMigration(base.BaseAlembicMigrationTest):

    def test_enum_has_new_values(self):
        expected_values = {
            'master_shell',
            'move_to_bootstrap',
            'erase_node',
        }

        result = db.execute(sa.text(
            'select unnest(enum_range(NULL::deployment_graph_tasks_type))'
        )).fetchall()
        self.assertTrue(expected_values.issubset((x[0] for x in result)))


class TestDeploymentHistoryMigration(base.BaseAlembicMigrationTest):

    def test_deployment_history_summary_field_exist(self):
        result = db.execute(sa.select([
            self.meta.tables['deployment_history']])).first()
        self.assertIn('summary', result)


class TestSplitDeploymentInfo(base.BaseAlembicMigrationTest):

    def test_split_deployment_info(self):
        node_di_table = self.meta.tables['node_deployment_info']
        res = db.execute(sa.select([node_di_table]))
        for data in res:
            self.assertEqual(jsonutils.loads(data.deployment_info),
                             DEPLOYMENT_INFO[data.task_id][data.node_uid])

        tasks_table = self.meta.tables['tasks']
        res = db.execute(sa.select([tasks_table]))
        for data in res:
            self.assertIsNone(data.deployment_info)


class TestReleasesUpdate(base.BaseAlembicMigrationTest):

    def test_attributes_metadata_update(self):
        result = db.execute(sa.select([
            self.meta.tables['releases']])).first()
        attrs = jsonutils.loads(result['attributes_metadata'])
        self.assertIn('editable', attrs)
        self.assertIn('storage', attrs['editable'])
        self.assertIn('auth_s3_keystone_ceph', attrs['editable']['storage'])
        self.assertIn('common', attrs['editable'])
        self.assertIn('run_ping_checker', attrs['editable']['common'])
        self.assertIn('propagate_task_deploy', attrs['editable']['common'])
        self.assertEqual(
            attrs['editable']['common']['propagate_task_deploy']['type'],
            'checkbox')
        self.assertEqual(
            "console=tty0 net.ifnames=1 biosdevname=0 rootdelay=90 nomodeset",
            attrs['editable']['kernel_params']['kernel']['value'])

    def test_networks_metadata_update(self):
        result = db.execute(sa.select([
            self.meta.tables['releases']])).first()
        nets = jsonutils.loads(result['networks_metadata'])
        self.assertIn('8086:10f8', nets['dpdk_drivers']['igb_uio'])

    def test_vmware_attributes_metadata_update(self):
        result = db.execute(sa.select([
            self.meta.tables['releases']])).first()
        attrs = jsonutils.loads(result['vmware_attributes_metadata'])

        fields = attrs['editable']['metadata'][0]['fields']
        self.assertItemsEqual(['vcenter_insecure', 'vcenter_ca_file'],
                              [f['name'] for f in fields])

        fields = attrs['editable']['metadata'][1]['fields']
        self.assertItemsEqual(['vcenter_insecure', 'ca_file'],
                              [f['name'] for f in fields])

        self.assertEqual(
            attrs['editable']['value'],
            {
                'availability_zones':
                    [
                        {
                            'vcenter_ca_file': {},
                            'vcenter_insecure': True,
                        },
                        {
                            'vcenter_ca_file': {},
                            'vcenter_insecure': True
                        }
                    ],
                'glance':
                    {
                        'ca_file': {},
                        'vcenter_insecure': True
                    }
            })


class TestClusterAttributesMigration(base.BaseAlembicMigrationTest):
    def test_deployment_info_migration(self):
        clusters_table = self.meta.tables['clusters']
        deployment_info = db.execute(
            sa.select([clusters_table.c.replaced_deployment_info])
        ).fetchone()[0]
        self.assertNotIsInstance(deployment_info, list)


class TestDeploymentSequencesMigration(base.BaseAlembicMigrationTest):
    def test_deployment_sequences_table_exists(self):
        deployment_sequences = self.meta.tables['deployment_sequences']
        release_id = db.execute(
            sa.select([self.meta.tables['releases'].c.id])
        ).fetchone()[0]
        db.execute(
            deployment_sequences.insert(),
            [{
                'release_id': release_id,
                'name': 'test',
                'graphs': '["test_graph"]',
            }]
        )
        result = db.execute(sa.select([
            deployment_sequences.c.name, deployment_sequences.c.graphs
        ]).where(deployment_sequences.c.name == 'test')).fetchone()
        self.assertEqual('test', result[0])
        self.assertEqual('["test_graph"]', result[1])
        with self.assertRaises(sa_exc.IntegrityError):
            db.execute(
                deployment_sequences.insert(),
                [{
                    'name': 'test',
                    'graphs': '["test_graph2"]',
                }]
            )


class TestReleaseStateMigration(base.BaseAlembicMigrationTest):
    def test_state_transition(self):
        result = db.execute(sa.select([
            self.meta.tables['releases'].c.state,
            self.meta.tables['releases'].c.version,
        ])).fetchall()

        for res, version in result:
            if StrictVersion(version.split('-')[1]) < StrictVersion('9.0'):
                self.assertEqual(res, consts.RELEASE_STATES.manageonly)
