# coding: utf-8

# Copyright 2016 Mirantis, Inc.
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

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base
from oslo_serialization import jsonutils
import sqlalchemy as sa

_prepare_revision = 'f2314e5d63c9'
_test_revision = '675105097a69'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)

    prepare()
    db.commit()

    alembic.command.downgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()
    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2015.1-8.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'networks_metadata': jsonutils.dumps({
                'neutron': {
                    'networks': [],
                    'config': {}
                }
            }),
            'volumes_metadata': jsonutils.dumps(
                {'rule_to_pick_boot_disk': [
                    {'type': 'very_important_rule'}
                ]})
        }])

    release_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test_cluster',
            'release_id': release_id,
            'mode': 'ha_compact',
            'status': 'new',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '10.0',
            'deployment_tasks': '[]',
            'replaced_deployment_info': '[]'
        }]
    )

    db.commit()


class TestDropRulesToPickBootableDisk(base.BaseAlembicMigrationTest):

    def test_drop_rule_to_pick_bootable_disk(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.volumes_metadata])
        ).fetchone()[0]
        volumes_metadata = jsonutils.loads(result)
        self.assertNotIn('rule_to_pick_boot_disk', volumes_metadata)


class TestTasksSchemaDowngrade(base.BaseAlembicMigrationTest):

    def test_dry_run_field_does_no_exist(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [{
                'uuid': 'fake_task_uuid_0',
                'name': 'dump',
                'status': 'pending'
            }]
        )

        result = db.execute(sa.select([self.meta.tables['tasks']])).first()
        self.assertNotIn('dry_run', result)

    def test_graph_type_field_does_no_exist(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [{
                'uuid': 'fake_task_uuid_0',
                'name': 'dump',
                'status': 'pending'
            }]
        )

        result = db.execute(sa.select([self.meta.tables['tasks']])).first()
        self.assertNotIn('graph_type', result)


class TestNodeErrorTypeMigration(base.BaseAlembicMigrationTest):

    def test_error_type_is_enum(self):
        nodes_table = self.meta.tables['nodes']
        self.assertEqual(
            'node_error_type', nodes_table.c.error_type.type.name
        )
        result = db.execute(sa.text(
            'select unnest(enum_range(NULL::node_error_type))'
        )).fetchall()
        self.assertEqual(
            {'deploy', 'provision', 'deletion', 'discover', 'stop_deployment'},
            {x[0] for x in result},
        )


class TestDeploymentGraphsDowngrade(base.BaseAlembicMigrationTest):

    def test_new_columns_does_not_exist(self):
        graphs_table = self.meta.tables['deployment_graphs']
        self.assertNotIn('node_filter', graphs_table.c)
        self.assertNotIn('on_success', graphs_table.c)
        self.assertNotIn('on_error', graphs_table.c)
        self.assertNotIn('on_stop', graphs_table.c)


class TestOrchestratorTaskTypesDowngrade(base.BaseAlembicMigrationTest):

    def test_enum_does_not_have_new_values(self):
        expected_values = {
            'master_shell',
            'move_to_bootstrap',
            'erase_node',
        }

        result = db.execute(sa.text(
            'select unnest(enum_range(NULL::deployment_graph_tasks_type))'
        )).fetchall()
        self.assertFalse(
            expected_values.intersection((x[0] for x in result))
        )


class TestDeploymentHistorySummaryField(base.BaseAlembicMigrationTest):

    def test_downgrade_tasks_noop(self):
        deployment_history = self.meta.tables['deployment_history']
        self.assertNotIn('summary', deployment_history.c)


class TestClusterAttributesDowngrade(base.BaseAlembicMigrationTest):
    def test_deployment_info_downgrade(self):
        clusters_table = self.meta.tables['clusters']
        deployment_info = db.execute(
            sa.select([clusters_table.c.replaced_deployment_info])
        ).fetchone()[0]
        self.assertEqual('[]', deployment_info)


class TestDeploymentSequencesDowngrade(base.BaseAlembicMigrationTest):
    def test_deployment_sequences_table_removed(self):
        self.assertNotIn('deployment_sequences', self.meta.tables)


class TestPluginAttributesMigration(base.BaseAlembicMigrationTest):
    def test_downgrade_plugin_with_nic_attributes(self):
        plugins_table = self.meta.tables['plugins']
        self.assertNotIn('bond_attributes_metadata', plugins_table.c)
        self.assertNotIn('nic_attributes_metadata', plugins_table.c)
        self.assertNotIn('node_attributes_metadata', plugins_table.c)
        releases_table = self.meta.tables['releases']
        self.assertNotIn('nic_attributes', releases_table.c)
        self.assertNotIn('bond_attributes', releases_table.c)
        node_nic_interfaces_table = self.meta.tables['node_nic_interfaces']
        self.assertNotIn('attributes', node_nic_interfaces_table.c)
        self.assertNotIn('meta', node_nic_interfaces_table.c)
        self.assertNotIn(
            'attributes', self.meta.tables['node_bond_interfaces'].c)
        self.assertNotIn(
            'node_cluster_plugins', self.meta.tables)
        self.assertNotIn(
            'node_bond_interface_cluster_plugins', self.meta.tables)
        self.assertNotIn(
            'node_nic_interface_cluster_plugins', self.meta.tables)
