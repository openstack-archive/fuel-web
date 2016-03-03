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
import sqlalchemy as sa
from sqlalchemy.exc import DataError, IntegrityError

from nailgun import consts
from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '43b2cb64dae6'
_test_revision = '11a9adc6d36a'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)

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

JSON_TASKS_AFTER_DB = [
    {
        'tasks': [],
        'groups': [],
        'condition': None,
        'parameters': '{}',
        'cross_depended_by': '[]',
        'reexecute_on': [],
        'required_for': [],
        'requires': ['post_deployment_start'],
        'refresh_on': [],
        'version': '1.0.0',
        'roles': [],
        'task_name': 'post_deployment_end',
        'type': 'stage',
        'cross_depends': '[]',
        '_custom': '{}',
    },
    {
        'tasks': [],
        'groups': [],
        'condition': None,
        'parameters': '{"strategy": {"type": "one_by_one"}}',
        'cross_depended_by': '[]',
        'reexecute_on': [],
        'required_for': ['deploy_end'],
        'requires': ['deploy_start'],
        'refresh_on': [],
        'version': '1.0.0',
        'roles': ['primary-controller'],
        'task_name': 'primary-controller',
        'type': 'group',
        'cross_depends': '[]',
        '_custom': '{}',
    },
    {
        'tasks': [],
        'groups': [],
        'condition': None,
        'parameters': '{}',
        'cross_depended_by': '["a", "b"]',
        'reexecute_on': [],
        'required_for': [],
        'requires': [],
        'refresh_on': [],
        'version': '1.0.0',
        'roles': [],
        'task_name': 'cross-dep-test',
        'type': 'puppet',
        'cross_depends': '["c", "d"]',
        '_custom': '{}',
    },
    {
        'tasks': [],
        'groups': [],
        'condition': None,
        'parameters': '{}',
        'cross_depended_by': '[]',
        'reexecute_on': [],
        'required_for': [],
        'requires': [],
        'refresh_on': [],
        'version': '1.0.0',
        'roles': [],
        'task_name': 'custom-test',
        'type': 'puppet',
        'cross_depends': '[]',
        '_custom': '{"test_pre": {"k": "v"}, "test_post": {"k": "v"}}',
    },

]


def prepare():
    meta = base.reflect_db_metadata()

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2015.1-8.0',
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
            'networks_metadata': jsonutils.dumps({
                'neutron': {
                    'networks': [
                        {
                            'assign_vip': True,
                        },
                    ]
                },
                'nova_network': {
                    'networks': [
                        {
                            'assign_vip': False,
                        },
                    ]
                },

            }),
            'network_roles_metadata': jsonutils.dumps([{
                'id': 'admin/vip',
                'default_mapping': 'fuelweb_admin',
                'properties': {
                    'subnet': True,
                    'gateway': False,
                    'vip': [
                        {
                            'name': 'release-vip1',
                        },
                        {
                            'name': 'release-vip2',
                            'namespace': 'release-vip2-namespace'
                        }
                    ]
                }
            }]),
            'is_deployable': True,
        }])
    releaseid = result.inserted_primary_key[0]

    db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test_env',
            'release_id': releaseid,
            'mode': 'ha_compact',
            'status': 'new',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '8.0',
            'deployment_tasks': jsonutils.dumps(JSON_TASKS)
        }])

    db.execute(
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

    db.execute(
        meta.tables['node_attributes'].insert(),
        [{
            'node_id': node_id,
            'vms_conf': jsonutils.dumps([
                {'cpu': 1, 'mem': 2},
                {'cpu': 1, 'mem': 2},
            ])
        }]
    )

    db.execute(
        meta.tables['ip_addrs'].insert(),
        [
            {
                'ip_addr': '192.168.0.2',
                'vip_type': 'management'
            },
            {
                'ip_addr': '192.168.1.2',
                'vip_type': 'haproxy'
            },
            {
                'ip_addr': '192.168.11.2',
                'vip_type': 'my-vip1',
                'namespace': 'my-namespace1'
            },
            {
                'ip_addr': '192.168.12.2',
                'vip_type': 'my-vip2',
                'namespace': 'my-namespace2'
            },
            {
                'ip_addr': '192.168.13.2',
                'vip_type': 'my-vip3',
                'namespace': 'my-namespace3'
            },
            {
                'ip_addr': '192.168.14.2',
                'vip_type': 'my-vip4',
                'namespace': 'my-namespace4'
            },
            {
                'ip_addr': '192.168.15.2',
                'vip_type': 'release-vip2'
            }
        ])

    db.execute(
        meta.tables['network_groups'].insert(),
        [{
            'name': 'public',
            'release': releaseid,
            'meta': jsonutils.dumps({'assign_vip': True})
        }])

    db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_a',
            'title': 'Test plugin A',
            'version': '2.0.0',
            'description': 'Test plugin A for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '4.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'deployment_tasks': jsonutils.dumps(JSON_TASKS),
            'fuel_version': jsonutils.dumps(['8.0']),
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

    db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_b',
            'title': 'Test plugin B',
            'version': '2.0.0',
            'description': 'Test plugin B for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '4.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['8.0']),
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

    db.commit()


class TestNodeGroupsMigration(base.BaseAlembicMigrationTest):

    def test_add_foreign_key_ondelete(self):
        expected_ondelete = {
            'attributes': {
                'attributes_cluster_id_fkey': 'CASCADE'
            },
            'cluster_changes': {
                'cluster_changes_id_fkey': 'CASCADE'
            },
            'nodegroups': {
                'nodegroups_cluster_id_fkey': 'CASCADE'
            },
            'vmware_attributes': {
                'vmware_attributes_cluster_id_fkey': 'CASCADE'
            },
            'networking_configs': {
                'networking_configs_cluster_id_fkey': 'CASCADE'
            },
            'network_groups': {
                'network_groups_nodegroups_fk': 'CASCADE',
                'network_groups_release_fk': 'CASCADE'
            },
            'neutron_config': {
                'neutron_config_id_fkey': 'CASCADE',
            },
            'nodes': {
                'nodes_nodegroups_fk': 'SET NULL',
                'nodes_cluster_id_fkey': 'CASCADE',
            },
            'cluster_plugin_links': {
                'cluster_plugin_links_cluster_id_fkey': 'CASCADE'
            },
            'node_nic_interfaces': {
                'node_nic_interfaces_parent_id_fkey': 'SET NULL'
            },
            'openstack_configs': {
                'openstack_configs_cluster_id_fkey': 'CASCADE',
                'openstack_configs_node_id_fkey': 'SET NULL'
            },
            'plugin_links': {
                'plugin_links_plugin_id_fkey': 'CASCADE'
            },
            'tasks': {
                'tasks_cluster_id_fkey': 'CASCADE',
                'tasks_parent_id_fkey': 'CASCADE'
            },

        }

        for table, fkeys in expected_ondelete.items():
            constraints = self.meta.tables[table].constraints

            for constraint in constraints:
                if constraint.name in fkeys:
                    value = fkeys[constraint.name]
                    self.assertEqual(constraint.ondelete, value)


class TestVipMigration(base.BaseAlembicMigrationTest):
    def test_ip_addrs_vip_name_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['ip_addrs'].c.vip_name]))
        self.assertEqual(result.scalar(), "management")

    def test_ip_addrs_vip_namespace_exists(self):
        result = db.execute(
            sa.select([
                self.meta.tables['ip_addrs'].c.vip_name,
                self.meta.tables['ip_addrs'].c.vip_namespace
            ]))
        result = list(result)
        self.assertItemsEqual(
            (
                ('management', None,),
                ('haproxy', None,),
                ('my-vip1', 'my-namespace1',),
                ('my-vip2', 'my-namespace2',),
                ('my-vip3', 'my-namespace3',),
                ('my-vip4', 'my-namespace4',),
                # namespace has appeared from release network role
                ('release-vip2', 'release-vip2-namespace',),
            ),
            result
        )


class TestNodeRolesMigration(base.BaseAlembicMigrationTest):
    def test_category_is_injected_to_roles_meta(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.roles_metadata])
        )
        rel_row = result.fetchone()

        roles_metadata = jsonutils.loads(rel_row[0])

        role_groups = {
            'controller': 'base',
            'compute': 'compute',
            'virt': 'compute',
            'compute-vmware': 'compute',
            'ironic': 'compute',
            'cinder': 'storage',
            'cinder-block-device': 'storage',
            'cinder-vmware': 'storage',
            'ceph-osd': 'storage'
        }

        for role_name in roles_metadata:
            role_group = roles_metadata[role_name].get('group')
            self.assertEquals(
                role_group,
                role_groups.get(role_name, consts.NODE_ROLE_GROUPS.other)
            )


class TestMergeNodeAttributes(base.BaseAlembicMigrationTest):

    def test_node_attributes_not_exists(self):
        self.assertNotIn('node_attributes', self.meta.tables)

    def test_data_moved_into_nodes_table(self):
        nodes_table = self.meta.tables['nodes']
        records = list(db.execute(
            sa.select([nodes_table.c.vms_conf])))

        for record in records:
            self.assertEqual(
                jsonutils.loads(record[0]),
                [
                    {'cpu': 1, 'mem': 2},
                    {'cpu': 1, 'mem': 2},
                ]
            )


class TestNodeAttributesMigration(base.BaseAlembicMigrationTest):

    def test_attributes_fields_exist(self):
        columns = [
            self.meta.tables['nodes'].c.attributes,
            self.meta.tables['releases'].c.node_attributes,
        ]

        for column in columns:
            db_values = db.execute(sa.select([column])).fetchone()
            for db_value in db_values:
                self.assertEqual(db_value, '{}')


class TestClusterStatusMigration(base.BaseAlembicMigrationTest):
    def test_cluster_status_upgraded(self):
        clusters_table = self.meta.tables['clusters']
        columns = [clusters_table.c.id, clusters_table.c.status]
        cluster = db.execute(sa.select(columns)).fetchone()

        db.execute(clusters_table.update().where(
            clusters_table.c.id == cluster.id
        ).values(status=consts.CLUSTER_STATUSES.partially_deployed))


class TestRemoveWizardMetadata(base.BaseAlembicMigrationTest):

    def test_wizard_metadata_does_not_exist_in_releases(self):
        releases_table = self.meta.tables['releases']
        self.assertNotIn('wizard_metadata', releases_table.c)


class TestDeploymentGraphMigration(
        base.BaseAlembicMigrationTest, base.DeploymentTasksTestMixin):

    def setUp(self):
        self.meta = base.reflect_db_metadata()

    def _insert_deployment_graph(self):
        result = db.execute(
            self.meta.tables['deployment_graphs'].insert(),
            [{'verbose_name': 'test_graph'}]
        )
        db.commit()
        deployment_graph_id = result.inserted_primary_key[0]
        return deployment_graph_id

    def test_deployment_graph_creation(self):
        result = db.execute(
            self.meta.tables['deployment_graphs'].insert(),
            [{'verbose_name': 'test_graph'}]
        )
        db.commit()
        graph_key = result.inserted_primary_key[0]
        result = db.execute(
            sa.select([
                self.meta.tables['deployment_graphs']
            ]))
        self.assertIn((graph_key, u'test_graph'), list(result))

    def test_deployment_graph_tasks_creation_success(self):
        deployment_graph_id = self._insert_deployment_graph()
        tasks = [
            {
                'task_name': 'task1',
                'deployment_graph_id': deployment_graph_id,
                'version': '2.0.0',
                'type': 'puppet',
                'condition': None,
                'requires': ['a', 'b'],
                'required_for': ['c', 'd'],
                'refresh_on': ['r1', 'r2'],
                'cross_depends': jsonutils.dumps(
                    [{'name': 'a'}, {'name': 'b'}]),
                'cross_depended_by': jsonutils.dumps(
                    [{'name': 'c'}, {'name': 'd'}]),
                'reexecute_on': ["nailgun_event1", "nailgun_event2"],
                'groups': ['group1', 'group2'],
                'roles': ['role1', 'role2'],
                'tasks': ['t1', 't2'],
                'parameters': jsonutils.dumps({'param1': 'val1'}),
                '_custom': jsonutils.dumps({}),
            },
            {
                'task_name': 'task2',
                'deployment_graph_id': deployment_graph_id,
                'version': '2.0.0',
                'type': 'puppet',
                'condition': None,
                'requires': ['task1'],
                'required_for': ['c', 'd'],
                'refresh_on': [],
                'cross_depends': jsonutils.dumps(
                    [{'name': 'task1'}]),
                'cross_depended_by': jsonutils.dumps(
                    [{'name': 'c'}, {'name': 'd'}]),
                'reexecute_on': ["nailgun_event3", "nailgun_event4"],
                'groups': ['group3', 'group4'],
                'roles': ['role3', 'role4'],
                'tasks': [],
                'parameters': jsonutils.dumps({'param2': 'val2'}),
                '_custom': jsonutils.dumps({}),
            }
        ]
        db.execute(self.meta.tables['deployment_graph_tasks'].insert(), tasks)
        db.commit()

        result = db.execute(
            sa.select([self.meta.tables['deployment_graph_tasks']]).where(
                sa.text(
                    'deployment_graph_tasks.deployment_graph_id = {0}'.format(
                        deployment_graph_id)
                )
            )
        )

        db_tasks = [dict(r) for r in result]
        for d in db_tasks:
            d.pop('id', None)

        self.assertItemsEqual(tasks, db_tasks)

    def test_minimal_task_creation_success(self):
        deployment_graph_id = self._insert_deployment_graph()
        db.execute(
            self.meta.tables['deployment_graph_tasks'].insert(),
            {
                'deployment_graph_id': deployment_graph_id,
                'task_name': 'minimal task',
                'type': consts.ORCHESTRATOR_TASK_TYPES.puppet
            },
        )

    def test_task_with_missing_required_fields_fail(self):
        deployment_graph_id = self._insert_deployment_graph()
        with self.assertRaisesRegexp(
            IntegrityError,
            'null value in column "type" violates not-null constraint'
        ):
            db.execute(
                self.meta.tables['deployment_graph_tasks'].insert(),
                {
                    'deployment_graph_id': deployment_graph_id,
                    'task_name': 'minimal task'
                })
        db.rollback()
        with self.assertRaisesRegexp(
            IntegrityError,
            'null value in column "task_name" violates not-null constraint'
        ):
            db.execute(
                self.meta.tables['deployment_graph_tasks'].insert(),
                {
                    'deployment_graph_id': deployment_graph_id,
                    'type': consts.ORCHESTRATOR_TASK_TYPES.puppet
                })
        db.rollback()

    def test_task_with_wrong_type_fail(self):
        deployment_graph_id = self._insert_deployment_graph()
        with self.assertRaisesRegexp(
            DataError,
            'invalid input value for enum deployment_graph_tasks_type'
        ):
            db.execute(
                self.meta.tables['deployment_graph_tasks'].insert(),
                {
                    'deployment_graph_id': deployment_graph_id,
                    'type': 'NOT EXISTING TYPE'
                })
        db.rollback()

    def test_release_graphs_is_created_from_json_tasks(self):
        query = sa.text("""
SELECT deployment_graph_tasks.*
    FROM deployment_graph_tasks
JOIN deployment_graphs
    ON deployment_graph_tasks.deployment_graph_id = deployment_graphs.id
JOIN release_deployment_graphs
    ON deployment_graphs.id = release_deployment_graphs.deployment_graph_id
JOIN releases
    ON release_deployment_graphs.release_id = releases.id
WHERE releases.id
    IN (SELECT id FROM releases WHERE releases.name = 'test_name')
        """)

        db_records = db.execute(query)
        results = []
        for record in db_records:
            result = dict(zip(record.keys(), record))
            result.pop('id', None)
            result.pop('deployment_graph_id', None)
            results.append(result)
        self._compare_tasks(JSON_TASKS_AFTER_DB, results)

    def test_cluster_graphs_is_created_from_json_tasks(self):
        self.maxDiff = None
        query = sa.text("""
SELECT deployment_graph_tasks.*
    FROM deployment_graph_tasks
JOIN deployment_graphs
    ON deployment_graph_tasks.deployment_graph_id = deployment_graphs.id
JOIN cluster_deployment_graphs
    ON deployment_graphs.id = cluster_deployment_graphs.deployment_graph_id
JOIN clusters
    ON cluster_deployment_graphs.cluster_id = clusters.id
WHERE clusters.id
    IN (SELECT id FROM clusters WHERE clusters.name = 'test_env')
        """)

        db_records = db.execute(query)
        results = []
        for record in db_records:

            result = dict(zip(record.keys(), record))
            result.pop('id', None)
            result.pop('deployment_graph_id', None)
            results.append(result)
        self._compare_tasks(JSON_TASKS_AFTER_DB, results)

    def test_plugins_graphs_is_created_from_json_tasks(self):
        query = sa.text("""
SELECT deployment_graph_tasks.*
    FROM deployment_graph_tasks
JOIN deployment_graphs
    ON deployment_graph_tasks.deployment_graph_id = deployment_graphs.id
JOIN plugin_deployment_graphs
    ON deployment_graphs.id = plugin_deployment_graphs.deployment_graph_id
JOIN plugins
    ON plugin_deployment_graphs.plugin_id = plugins.id
WHERE plugins.id
    IN (SELECT id FROM plugins WHERE plugins.name = 'test_plugin_a')
        """)

        db_records = db.execute(query)
        results = []
        for record in db_records:
            result = dict(zip(record.keys(), record))
            result.pop('id', None)
            result.pop('deployment_graph_id', None)
            results.append(result)
        self._compare_tasks(JSON_TASKS_AFTER_DB, results)
