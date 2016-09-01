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
from oslo_serialization import jsonutils
import sqlalchemy as sa

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
            'version': '2015.1-8.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'networks_metadata': jsonutils.dumps({
                'neutron': {
                    'networks': [],
                    'config': {}
                }
            }),
            'volumes_metadata': jsonutils.dumps({}),
            'attributes_metadata': jsonutils.dumps({})
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

    db.execute(
        meta.tables['tasks'].insert(),
        [
            {
                'id': 55,
                'uuid': '219eaafe-01a1-4f26-8edc-b9d9b0df06b3',
                'name': 'deployment',
                'status': 'running',
                'deployment_info': jsonutils.dumps({})
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

    db.commit()


class TestRulesToPickBootableDisk(base.BaseAlembicMigrationTest):

    def test_release_rules_to_pick_bootable_disk_creation(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.volumes_metadata])
        ).fetchone()[0]
        volumes_metadata = jsonutils.loads(result)
        self.assertIn('rule_to_pick_boot_disk', volumes_metadata)
        self.assertEquals(
            volumes_metadata['rule_to_pick_boot_disk'],
            rule_to_pick_bootdisk
        )


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


class TestDeploymentHistoryMigration(base.BaseAlembicMigrationTest):

    def test_deployment_history_summary_field_exist(self):
        result = db.execute(sa.select([
            self.meta.tables['deployment_history']])).first()
        self.assertIn('summary', result)


class TestClusterAttributesMigration(base.BaseAlembicMigrationTest):
    def test_deployment_info_migration(self):
        clusters_table = self.meta.tables['clusters']
        deployment_info = db.execute(
            sa.select([clusters_table.c.replaced_deployment_info])
        ).fetchone()[0]
        self.assertEqual('{}', deployment_info)


class TestReleasesUpdateFromFixture(base.BaseAlembicMigrationTest):

    def test_releases_update(self):
        result = db.execute(sa.select([
            self.meta.tables['releases']])).first()
        attrs = jsonutils.loads(result['attributes_metadata'])
        self.assertIn('editable', attrs)
        self.assertIn('storage', attrs['editable'])
        self.assertIn('auth_s3_keystone_ceph', attrs['editable']['storage'])
