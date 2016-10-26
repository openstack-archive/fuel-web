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
import six
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = 'c6edea552f1e'
_test_revision = 'dc8bc8751c42'


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
            'version': '2016.1-11.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'roles': jsonutils.dumps([
                'controller',
            ]),
            'roles_metadata': jsonutils.dumps({
                'controller': {
                    'name': 'Controller',
                },
            }),
            'is_deployable': True
        }])

    release_id = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test_env1',
            'release_id': release_id,
            'mode': 'ha_compact',
            'status': 'operational',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '10.0',
        }])
    cluster_id = result.inserted_primary_key[0]

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
            'fuel_version': jsonutils.dumps(['10.0']),
            'roles_metadata': jsonutils.dumps({
                'role_x': {
                    'name': 'role_x',
                    'has_primary': False
                },
            })
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
            'roles_metadata': jsonutils.dumps({
                'role_y': {
                    'name': 'role_y',
                    'has_primary': True,
                    'public_ip_required': True
                },
            })
        }]
    )
    plugin_b_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['cluster_plugins'].insert(),
        [
            {'cluster_id': cluster_id, 'plugin_id': plugin_a_id},
            {'cluster_id': cluster_id, 'plugin_id': plugin_b_id}
        ]
    )

    result = db.execute(
        meta.tables['nodes'].insert(),
        [{
            'id': 2,
            'uuid': 'fcd49872-3917-4a18-98f9-3f5acfe3fdec',
            'cluster_id': cluster_id,
            'group_id': None,
            'status': 'ready',
            'roles': ['role_x', 'role_y'],
            'primary_roles': ['role_y'],
            'meta': '{}',
            'mac': 'bb:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
        }]
    )
    result = db.execute(
        meta.tables['tags'].insert(),
        [
            {
                'tag': 'controller',
                'owner_id': release_id,
                'owner_type': 'release',
                'has_primary': True,
                'read_only': True
            },
            {
                'tag': 'compute',
                'owner_id': cluster_id,
                'owner_type': 'cluster',
                'has_primary': False,
                'read_only': True
            }
        ]
    )
    db.commit()


class TestTags(base.BaseAlembicMigrationTest):
    def test_plugins_tags_created_on_upgrade(self):
        tags = self.meta.tables['tags']
        tags_count = db.execute(
            sa.select(
                [sa.func.count(tags.c.id)]
            ).where(tags.c.owner_type == 'plugin')).fetchone()[0]

        self.assertEqual(tags_count, 2)

    def test_nodes_assigned_tags(self):
        tags = self.meta.tables['tags']
        node_tags = self.meta.tables['node_tags']

        query = sa.select([tags.c.tag, node_tags.c.is_primary]).select_from(
            sa.join(
                tags, node_tags,
                tags.c.id == node_tags.c.tag_id
            )
        ).where(
            node_tags.c.node_id == 2
        )

        res = db.execute(query)
        primary_tags = []
        tags = []
        for tag, is_primary in res:
            tags.append(tag)
            if is_primary:
                primary_tags.append(tag)
        self.assertItemsEqual(tags, ['role_x', 'role_y'])
        self.assertItemsEqual(primary_tags, ['role_y'])

    def test_plugins_role_metadata_changed(self):
        plugins = self.meta.tables['plugins']
        q_roles_meta = sa.select([plugins.c.roles_metadata])
        for role_meta in db.execute(q_roles_meta):
            for role, meta in six.iteritems(jsonutils.loads(role_meta[0])):
                self.assertEqual(meta['tags'], [role])

    def test_cluster_tag_metada_updated(self):
        tags = self.meta.tables['tags']
        releases = self.meta.tables['releases']
        plugins = self.meta.tables['plugins']
        tags_meta = db.execute(
            sa.select(
                [tags.c.tag, tags.c.owner_id, tags.c.owner_type,
                 tags.c.public_ip_required, tags.c.public_for_dvr_required]
            )
        ).fetchall()
        release_q = sa.select([releases.c.id, releases.c.roles_metadata,
                               sa.text("\'release\'")])

        plugin_q = sa.select([plugins.c.id, plugins.c.roles_metadata,
                              sa.text("\'plugin\'")])

        res = db.execute(release_q.union(plugin_q))
        for tag, owner_id, owner_type, private_ip_r, public_for_dvr_r\
                in tags_meta:
            for own_id, roles_meta, own_type in res:
                if owner_type == own_type and owner_id == own_id:
                    for role, role_meta in \
                            six.iteritems(jsonutils.loads(roles_meta)):
                        if tag in role_meta.get('tags', []):
                            self.assertEqual(private_ip_r,
                                             role_meta.get(
                                                 'public_ip_required',
                                                 False))
                            self.assertEqual(public_for_dvr_r,
                                             role_meta.get(
                                                 'public_for_dvr_required',
                                                 False))
