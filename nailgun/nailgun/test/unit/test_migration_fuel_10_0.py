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

import alembic
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '675105097a69'
_test_revision = 'c6edea552f1e'

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
        }])
    release_id = result.inserted_primary_key[0]

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
                'fuel_version': '10.0'
            }])
        cluster_ids.append(result.inserted_primary_key[0])

    result = db.execute(
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
    plugin_a_id = result.inserted_primary_key[0]

    result = db.execute(
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
    plugin_b_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['cluster_plugin_links'].insert(),
        [
            {
                'cluster_id': cluster_ids[0],
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description',
                'hidden': False
            },
            # this is duplicate, should be deleted during migration
            {
                'cluster_id': cluster_ids[1],
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description_duplicate',
                'hidden': False
            },
            # duplicate by URL but in another cluster, should
            # not be deleted
            {
                'cluster_id': cluster_ids[0],
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description',
                'hidden': False
            }
        ]
    )

    db.execute(
        meta.tables['plugin_links'].insert(),
        [
            {
                'plugin_id': plugin_a_id,
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description',
                'hidden': False
            },
            # this is duplicate, should be deleted during migration
            {
                'plugin_id': plugin_b_id,
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description_duplicate',
                'hidden': False
            }
        ]
    )

    db.commit()


class TestPluginLinksConstraints(base.BaseAlembicMigrationTest):
    # see initial data in setup section
    def test_plugin_links_duplicate_cleanup(self):
        links_count = db.execute(
            sa.select(
                [sa.func.count(self.meta.tables['plugin_links'].c.id)]
            )).fetchone()[0]
        self.assertEqual(links_count, 1)

    def test_cluster_plugin_links_duplicate_cleanup(self):
        links_count = db.execute(
            sa.select(
                [sa.func.count(self.meta.tables['cluster_plugin_links'].c.id)]
            )).fetchone()[0]
        self.assertEqual(links_count, 2)


class TestTasksSnapshotField(base.BaseAlembicMigrationTest):
    def test_fields_exist(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [{
                'uuid': 'fake_task_uuid_0',
                'name': 'dump',
                'status': 'pending',
                'tasks_snapshot': '[{"id":"taskid","type":"puppet"}]'
            }]
        )
        result = db.execute(
            sa.select([
                self.meta.tables['tasks'].c.tasks_snapshot,
            ])
        ).first()
        self.assertIsNotNone(result['tasks_snapshot'])
