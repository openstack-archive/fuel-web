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
from oslo_serialization import jsonutils
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
import uuid

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


_prepare_revision = '1e50a4903910'
_test_revision = '43b2cb64dae6'


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
            'version': '2014.2.2-6.1',
            'operating_system': 'ubuntu',
            'state': 'available',
            'roles': jsonutils.dumps([
                'controller',
                'compute',
                'mongo',
            ]),
            'roles_metadata': jsonutils.dumps({
                'controller': {
                    'name': 'Controller',
                    'description': 'Controller role',
                    'has_primary': True,
                },
                'zabbix-server': {
                    'name': 'Zabbix Server',
                    'description': 'Zabbix Server role'
                },
                'cinder': {
                    'name': 'Cinder',
                    'description': 'Cinder role'
                },
                'mongo': {
                    'name': 'Telemetry - MongoDB',
                    'description': 'mongo is',
                    'has_primary': True,
                }
            }),
            'attributes_metadata': jsonutils.dumps({}),
            'networks_metadata': jsonutils.dumps({
                'bonding': {
                    'properties': {
                        'linux': {
                            'mode': [
                                {
                                    "values": ["balance-rr",
                                               "active-backup",
                                               "802.3ad"]
                                },
                                {
                                    "values": ["balance-xor",
                                               "broadcast",
                                               "balance-tlb",
                                               "balance-alb"],
                                    "condition": "'experimental' in "
                                                 "version:feature_groups"
                                }
                            ]
                        }
                    }
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
            'fuel_version': '6.1',
        }])
    clusterid = result.inserted_primary_key[0]

    db.execute(
        meta.tables['nodegroups'].insert(),
        [
            {'cluster_id': clusterid, 'name': 'test_nodegroup_a'},
            {'cluster_id': clusterid, 'name': 'test_nodegroup_a'},
            {'cluster_id': clusterid, 'name': 'test_nodegroup_b'},
            {'cluster_id': clusterid, 'name': 'test_nodegroup_b'},
        ])

    result = db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_a',
            'title': 'Test plugin A',
            'version': '1.0.0',
            'description': 'Test plugin A for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '3.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['6.1', '7.0']),
        }]
    )
    pluginid_a = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_b',
            'title': 'Test plugin B',
            'version': '1.0.0',
            'description': 'Test plugin B for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '3.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['6.1', '7.0']),
        }]
    )
    pluginid_b = result.inserted_primary_key[0]

    db.execute(
        meta.tables['cluster_plugins'].insert(),
        [
            {
                'cluster_id': clusterid,
                'plugin_id': pluginid_a
            },
            {
                'cluster_id': clusterid,
                'plugin_id': pluginid_b
            }
        ]
    )

    db.execute(
        meta.tables['attributes'].insert(),
        [{
            'cluster_id': clusterid,
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
                        'enabled': False,
                        'toggleable': True,
                        'weight': 80,
                    }
                }
            }),
            'generated': jsonutils.dumps({}),
        }])

    db.commit()


class TestNodeGroupsMigration(base.BaseAlembicMigrationTest):

    def test_name_cluster_unique_constraint_migration(self):
        names = db.execute(
            sa.select([self.meta.tables['nodegroups'].c.name])).fetchall()
        self.assertIn(('test_nodegroup_a_0',), names)
        self.assertIn(('test_nodegroup_a_1',), names)
        self.assertIn(('test_nodegroup_b_0',), names)
        self.assertIn(('test_nodegroup_b_1',), names)

    def test_unique_name_fields_insert_duplicated(self):
        nodegroup = db.execute(
            sa.select([self.meta.tables['nodegroups'].c.cluster_id,
                       self.meta.tables['nodegroups'].c.name])).fetchone()
        with self.assertRaisesRegexp(IntegrityError,
                                     'duplicate key value violates unique '
                                     'constraint "_name_cluster_uc"'):
            db.execute(self.meta.tables['nodegroups'].insert(),
                       [{'cluster_id': nodegroup['cluster_id'],
                         'name': nodegroup['name']}])

    def test_unique_name_fields_insert_unique(self):
        nodegroup = db.execute(
            sa.select([self.meta.tables['nodegroups'].c.cluster_id,
                       self.meta.tables['nodegroups'].c.name])).fetchone()
        db.execute(self.meta.tables['nodegroups'].insert(),
                   [{'cluster_id': nodegroup['cluster_id'],
                     'name': uuid.uuid4()}])


class TestClusterPluginsMigration(base.BaseAlembicMigrationTest):

    def _get_enabled(self, plugin_name):
        plugins = self.meta.tables['plugins']
        cluster_plugins = self.meta.tables['cluster_plugins']

        query = sa.select([cluster_plugins.c.enabled])\
            .select_from(
                sa.join(
                    cluster_plugins, plugins,
                    cluster_plugins.c.plugin_id == plugins.c.id))\
            .where(plugins.c.name == plugin_name)
        return db.execute(query).fetchone()[0]

    def test_plugin_a_is_enabled(self):
        enabled = self._get_enabled('test_plugin_a')
        self.assertTrue(enabled)

    def test_plugin_b_is_disabled(self):
        enabled = self._get_enabled('test_plugin_b')
        self.assertFalse(enabled)

    def test_moving_plugin_attributes(self):
        clusters = self.meta.tables['clusters']
        attributes = self.meta.tables['attributes']
        plugins = self.meta.tables['plugins']
        cluster_plugins = self.meta.tables['cluster_plugins']

        query = sa.select([attributes.c.editable])\
            .select_from(
                sa.join(
                    attributes, clusters,
                    attributes.c.cluster_id == clusters.c.id))
        result = jsonutils.loads(db.execute(query).fetchone()[0])
        self.assertItemsEqual(result, {})

        query = sa.select([cluster_plugins.c.attributes])\
            .select_from(
                sa.join(
                    cluster_plugins, plugins,
                    cluster_plugins.c.plugin_id == plugins.c.id))\
            .where(plugins.c.name == 'test_plugin_a')
        result = jsonutils.loads(db.execute(query).fetchone()[0])
        self.assertItemsEqual(result['metadata'],
                              {'weight': 70, 'toggleable': True})
