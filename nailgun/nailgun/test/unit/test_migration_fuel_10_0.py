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

_prepare_revision = 'f2314e5d63c9'
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

VMWARE_ATTRIBUTES_METADATA = {
    'editable': {
        'metadata': [
            {
                'name': 'availability_zones',
                'fields': []
            },
            {
                'name': 'glance',
                'fields': []
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
            'is_deployable': True,
            'vmware_attributes_metadata':
                jsonutils.dumps(VMWARE_ATTRIBUTES_METADATA)
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

    node_id = 1
    result = db.execute(
        meta.tables['nodes'].insert(),
        [{
            'id': node_id,
            'uuid': '26b508d0-0d76-4159-bce9-f67ec2765480',
            'cluster_id': None,
            'group_id': None,
            'status': 'discover',
            'meta': '{}',
            'mac': 'aa:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
        }]
    )

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

    result = db.execute(
        meta.tables['tasks'].insert(),
        [
            {
                'id': 55,
                'uuid': '219eaafe-01a1-4f26-8edc-b9d9b0df06b3',
                'name': 'deployment',
                'status': 'running',
                'deployment_info': jsonutils.dumps(DEPLOYMENT_INFO[55])
            },
            {
                'id': 56,
                'uuid': 'a45fbbcd-792c-4245-a619-f4fb2f094d38',
                'name': 'deployment',
                'status': 'running',
                'deployment_info': jsonutils.dumps(DEPLOYMENT_INFO[56])
            }
        ]
    )

    result = db.execute(
        meta.tables['nodes'].insert(),
        [{
            'id': 2,
            'uuid': 'fcd49872-3917-4a18-98f9-3f5acfe3fdec',
            'cluster_id': cluster_ids[0],
            'group_id': None,
            'status': 'ready',
            'roles': ['controller', 'ceph-osd'],
            'meta': '{}',
            'mac': 'bb:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
        }]
    )

    TestRequiredComponentTypesField.prepare(meta)
    db.commit()


class TestTagExistingNodes(base.BaseAlembicMigrationTest):
    def test_tags_created_on_upgrade(self):
        tags_count = db.execute(
            sa.select(
                [sa.func.count(self.meta.tables['tags'].c.id)]
            )).fetchone()[0]

        self.assertEqual(tags_count, 11)

    def test_nodes_assigned_tags(self):
        tags = self.meta.tables['tags']
        node_tags = self.meta.tables['node_tags']

        query = sa.select([tags.c.tag]).select_from(
            sa.join(
                tags, node_tags,
                tags.c.id == node_tags.c.tag_id
            )
        ).where(
            node_tags.c.node_id == 2
        )

        res = db.execute(query)
        tags = [t[0] for t in res]
        self.assertItemsEqual(tags, ['controller', 'ceph-osd'])


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


class TestReleasesUpdate(base.BaseAlembicMigrationTest):
    def test_vmware_attributes_metadata_update(self):
        result = db.execute(sa.select([
            self.meta.tables['releases']])).first()
        attrs = jsonutils.loads(result['vmware_attributes_metadata'])

        fields = attrs['editable']['metadata'][0]['fields']
        self.assertItemsEqual(['vcenter_security_disabled'],
                              [f['name'] for f in fields])

        fields = attrs['editable']['metadata'][1]['fields']
        self.assertItemsEqual(['vcenter_security_disabled'],
                              [f['name'] for f in fields])

        self.assertEqual(
            attrs['editable']['value'],
            {
                'availability_zones':
                    [
                        {
                            'vcenter_security_disabled': True,
                        },
                        {
                            'vcenter_security_disabled': True,
                        }
                    ],
                'glance':
                    {
                        'vcenter_security_disabled': True,
                    }
            })
