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

import datetime

import alembic
import six
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base
from oslo_serialization import jsonutils

_prepare_revision = '3763c404ca48'
_test_revision = 'f2314e5d63c9'


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
            'version': 'mitaka-9.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'networks_metadata': jsonutils.dumps({
                'neutron': {
                    'networks': [],
                    'config': {}
                }
            }),
            'roles_metadata': jsonutils.dumps({
                'controller': {
                    'name': 'controller',
                    'has_primary': False,
                    'tags': ['controller']
                },
            }),
            'tags_metadata': jsonutils.dumps({
                'controller': {
                    'has_primary': False
                },
            })
        }])

    release_id = result.inserted_primary_key[0]

    db.execute(
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
            'fuel_version': jsonutils.dumps(['10.0']),
            'roles_metadata': jsonutils.dumps({
                'role_x': {
                    'name': 'role_x',
                    'has_primary': False,
                    'tags': ['role_x']
                },
            }),
            'tags_metadata': jsonutils.dumps({
                'role_x': {
                    'has_primary': False
                },
            })
        }]
    )

    result = db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test_cluster',
            'release_id': release_id,
            'mode': 'ha_compact',
            'status': 'operational',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '10.0',
            'deployment_tasks': '[]',
            'replaced_deployment_info': '[]'
        }]
    )

    cluster_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['nodes'].insert(),
        [{
            'uuid': 'fcd49872-3917-4a18-98f9-3f5acfe3fdec',
            'cluster_id': cluster_id,
            'group_id': None,
            'status': 'ready',
            'roles': ['controller', 'ceph-osd'],
            'meta': '{}',
            'mac': 'bb:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
        }]
    )

    db.commit()


class TestNodeTagging(base.BaseAlembicMigrationTest):

    def test_downgrade_tags_metadata(self):
        releases_table = self.meta.tables['releases']
        plugins_table = self.meta.tables['plugins']
        self.assertNotIn('tags_metadata', releases_table.c)
        self.assertNotIn('tags_metadata', plugins_table.c)
        self.assertNotIn('tags', self.meta.tables)
        self.assertNotIn('node_tags', self.meta.tables)

    def test_tags_are_absent_in_role_meta(self):
        plugins = self.meta.tables['plugins']
        releases = self.meta.tables['releases']
        q_roles_meta = (sa.select([plugins.c.roles_metadata]).union(
                        sa.select([releases.c.roles_metadata])))
        for role_meta in db.execute(q_roles_meta):
            for role, meta in six.iteritems(jsonutils.loads(role_meta[0])):
                self.assertNotIn('tags', meta)
