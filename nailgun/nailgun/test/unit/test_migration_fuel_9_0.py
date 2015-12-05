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
from nailgun import consts
from oslo_serialization import jsonutils
import sqlalchemy as sa

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


def prepare():
    meta = base.reflect_db_metadata()

    roles_metadata = jsonutils.dumps({
        "mongo": {
            "name": "Mongo",
            "description": "Mongo role"
        }
    })

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': '2015.1-8.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'roles_metadata': roles_metadata,
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
                },
                'nova_network': {
                    'networks': [
                        {
                            'assign_vip': False,
                        },
                    ]
                },

            }),
            'is_deployable': True,
        }])
    releaseid = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test_env',
            'release_id': releaseid,
            'mode': 'ha_compact',
            'status': 'new',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '8.0',
        }])
    cluster_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['attributes'].insert(),
        [{
            'cluster_id': cluster_id,
            'editable': '{"common": {}}',
            'generated': '{"cobbler": {"profile": "ubuntu_1204_x86_64"}}',
        }])

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
                'vip_type': 'my-vip'
            },
            {
                'ip_addr': '192.168.12.2',
                'vip_type': 'my-vip1'
            },
            {
                'ip_addr': '192.168.13.2',
                'vip_type': 'my-vip2'
            }
        ])

    db.execute(
        meta.tables['network_groups'].insert(),
        [{
            'name': 'public',
            'release': releaseid,
            'meta': jsonutils.dumps({'assign_vip': True})
        }])

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
            'fuel_version': jsonutils.dumps(['8.0']),
            'network_roles_metadata': jsonutils.dumps([{
                'id': 'admin/vip',
                'default_mapping': consts.NETWORKS.fuelweb_admin,
                'properties': {
                    'subnet': True,
                    'gateway': False,
                    'vip': [
                        {
                            'name': 'my-vip',
                            'namespace': 'my-namespace',
                        },
                        {
                            'name': 'my-vip1',
                            'namespace': 'my-namespace1',
                        }
                    ]
                }
            }])
        }]
    )
    pluginid_a = result.inserted_primary_key[0]

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
                'default_mapping': consts.NETWORKS.fuelweb_admin,
                'properties': {
                    'subnet': True,
                    'gateway': False,
                    'vip': [
                        {
                            'name': 'my-vip',
                            'namespace': 'my-namespace',
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
    pluginid_b = result.inserted_primary_key[0]

    db.execute(
        meta.tables['cluster_plugins'].insert(),
        [
            {
                'cluster_id': cluster_id,
                'plugin_id': pluginid_a,
                'enabled': True
            },
            {
                'cluster_id': cluster_id,
                'plugin_id': pluginid_b,
                'enabled': True
            }
        ]
    )

    db.execute(
        meta.tables['attributes'].insert(),
        [{
            'cluster_id': cluster_id,
            'editable': jsonutils.dumps({
                'test_plugin_a': {
                    'metadata': {
                        'plugin_id': pluginid_a,
                        'enabled': True,
                        'toggleable': True,
                        'weight': 70,
                    }
                },
                'test_plugin_b': {
                    'metadata': {
                        'plugin_id': pluginid_b,
                        'enabled': True,
                        'toggleable': True,
                        'weight': 80,
                    }
                }
            }),
            'generated': jsonutils.dumps({}),
        }])

    db.commit()


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
        self.assertIn(('my-vip', 'my-namespace',), result)
        self.assertIn(('my-vip1', 'my-namespace1',), result)
        self.assertIn(('my-vip2', 'my-namespace2',), result)

    def test_ip_addrs_is_user_assigned_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['ip_addrs'].c.is_user_defined]))
        self.assertEqual(False, result.scalar())
