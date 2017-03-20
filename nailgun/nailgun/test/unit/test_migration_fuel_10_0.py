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
from sqlalchemy.exc import IntegrityError

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '3763c404ca48'
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

DEPLOYMENT_INFO = {
    55: {
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
    56: {
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
            'vmware_attributes_metadata': 'test_meta',
            'version': '2015.1-10.0',
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
            'is_deployable': True
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
                'fuel_version': '10.0',
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
            'fuel_version': jsonutils.dumps(['10.0']),
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
            'fuel_version': jsonutils.dumps(['10.0']),
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
        meta.tables['cluster_plugins'].insert(),
        [
            {'cluster_id': cluster_ids[0], 'plugin_id': plugin_a_id},
            {'cluster_id': cluster_ids[0], 'plugin_id': plugin_b_id}
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

    db.execute(
        meta.tables['cluster_changes'].insert(),
        [
            {
                'cluster_id': cluster_ids[0],
                'node_id': node_id,
                'name': 'networks',
                'vmware_attributes': 'vmware_attributes'
            }
        ]
    )

    db.execute(
        meta.tables['vmware_attributes'].insert(),
        [
            {
                'cluster_id': cluster_ids[0],
                'editable': 'test_data'
            }
        ]
    )

    TestRequiredComponentTypesField.prepare(meta)
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


class TestRequiredComponentTypesField(base.BaseAlembicMigrationTest):
    release_name = 'test_release'
    version = '2015.1-10.0'

    @classmethod
    def prepare(cls, meta):
        db.execute(
            meta.tables['releases'].insert(),
            [{
                'name': cls.release_name,
                'version': cls.version,
                'operating_system': 'ubuntu',
                'state': 'available',
                'roles_metadata': '{}',
                'is_deployable': True
            }])

    def test_upgrade_release_required_component_types(self):
        releases_table = self.meta.tables['releases']
        result = db.execute(
            sa.select([releases_table.c.required_component_types]).
            where(releases_table.c.name == self.release_name).
            where(releases_table.c.version == self.version)).fetchone()
        self.assertEqual(jsonutils.loads(result['required_component_types']),
                         ['hypervisor', 'network', 'storage'])

    def test_not_nullable_required_component_types(self):
        with self.assertRaisesRegexp(
                IntegrityError,
                'null value in column "required_component_types" '
                'violates not-null constraint'
        ):
            db.execute(
                self.meta.tables['releases'].insert(),
                {
                    'name': 'test_release',
                    'version': '2015.1-10.0',
                    'operating_system': 'ubuntu',
                    'state': 'available',
                    'roles_metadata': '{}',
                    'is_deployable': True,
                    'required_component_types': None
                })
        db.rollback()


class TestRemoveVMware(base.BaseAlembicMigrationTest):
    def test_vmware_attributes_metadata_not_exist_in_releases(self):
        releases_table = self.meta.tables['releases']
        self.assertNotIn('vmware_attributes_metadata', releases_table.c)

    def test_there_is_no_table_vmware_attributes(self):
        self.assertNotIn('vmware_attributes', self.meta.tables)

    def test_vmware_attributes_not_exist_in_cluster_changes(self):
        cluster_changes_table = self.meta.tables['cluster_changes']
        self.assertNotIn('vmware_attributes', cluster_changes_table.c)

    def test_cluster_changes_enum_doesnt_have_old_values(self):
        result = db.execute(sa.text(
            'select unnest(enum_range(NULL::possible_changes))'
        )).fetchall()
        self.assertNotIn('vmware_attributes', [x[0] for x in result])
