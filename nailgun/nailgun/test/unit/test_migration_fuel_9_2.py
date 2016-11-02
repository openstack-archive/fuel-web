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

_prepare_revision = 'f2314e5d63c9'
_test_revision = '3763c404ca48'


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
            'deployment_tasks': '{}',
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

    result = db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test',
            'release_id': release_id,
            'mode': 'ha_compact',
            'status': 'new',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '10.0',
            'deployment_tasks': '{}'
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
                'role_y': {
                    'name': 'role_y',
                    'has_primary': True
                },
            })
        }]
    )
    plugin_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['cluster_plugins'].insert(),
        [
            {'cluster_id': cluster_id, 'plugin_id': plugin_id}
        ]
    )

    node_id = 1
    db.execute(
        meta.tables['nodes'].insert(),
        [{
            'id': node_id,
            'uuid': 'fcd49872-3917-4a18-98f9-3f5acfe3fdec',
            'cluster_id': cluster_id,
            'group_id': None,
            'status': 'ready',
            'roles': ['controller', 'ceph-osd', 'role_x', 'role_y'],
            'primary_roles': ['controller', 'role_y'],
            'meta': '{}',
            'mac': 'bb:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
        }]
    )

    db.commit()


class TestTagExistingNodes(base.BaseAlembicMigrationTest):
    def test_tags_created_on_upgrade(self):
        tags_count = db.execute(
            sa.select(
                [sa.func.count(self.meta.tables['tags'].c.id)]
            )).fetchone()[0]

        self.assertEqual(tags_count, 13)

    def test_nodes_assigned_tags(self):
        tags = self.meta.tables['tags']
        node_tags = self.meta.tables['node_tags']

        query = sa.select([tags.c.tag, node_tags.c.is_primary]).select_from(
            sa.join(
                tags, node_tags,
                tags.c.id == node_tags.c.tag_id
            )
        ).where(
            node_tags.c.node_id == 1
        )

        res = db.execute(query)
        primary_tags = []
        tags = []
        for tag, is_primary in res:
            tags.append(tag)
            if is_primary:
                primary_tags.append(tag)
        self.assertItemsEqual(tags, ['controller', 'ceph-osd',
                                     'role_x', 'role_y'])
        self.assertItemsEqual(primary_tags, ['controller', 'role_y'])

    def test_role_metadata_changed(self):
        plugins = self.meta.tables['plugins']
        releases = self.meta.tables['releases']
        q_roles_meta = (sa.select([plugins.c.roles_metadata]).union(
                        sa.select([releases.c.roles_metadata])))
        for role_meta in db.execute(q_roles_meta):
            for role, meta in six.iteritems(jsonutils.loads(role_meta[0])):
                self.assertEqual(meta['tags'], [role])


class TestReleasesUpdate(base.BaseAlembicMigrationTest):
    def test_vmware_attributes_metadata_update(self):
        result = db.execute(sa.select([
            self.meta.tables['releases']])).first()
        attrs = jsonutils.loads(result['vmware_attributes_metadata'])

        fields = attrs['editable']['metadata'][0]['fields']
        self.assertItemsEqual(['vcenter_unsecure', 'vcenter_ca_file'],
                              [f['name'] for f in fields])

        fields = attrs['editable']['metadata'][1]['fields']
        self.assertItemsEqual(['vcenter_unsecure', 'ca_file'],
                              [f['name'] for f in fields])

        self.assertEqual(
            attrs['editable']['value'],
            {
                'availability_zones':
                    [
                        {
                            'vcenter_ca_file': {},
                            'vcenter_unsecure': True,
                        },
                        {
                            'vcenter_ca_file': {},
                            'vcenter_unsecure': True
                        }
                    ],
                'glance':
                    {
                        'ca_file': {},
                        'vcenter_unsecure': True
                    }
            })
