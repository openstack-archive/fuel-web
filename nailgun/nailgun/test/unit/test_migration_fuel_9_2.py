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
from nailgun.utils import migration

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

ATTRIBUTES_METADATA = {
    'editable': {
        'common': {}
    }
}

SECURITY_GROUP = {
    'value': 'iptables_hybrid',
    'values': [
        {
            'data': 'openvswitch',
            'label': 'Open vSwitch Firewall Driver',
            'description': 'Choose this type of firewall driver if you'
                           ' use OVS Bridges for networking needs.'
        },
        {
            'data': 'iptables_hybrid',
            'label': 'Iptables-based Firewall Driver',
            'description': 'Choose this type of firewall driver if you'
                           ' use Linux Bridges for networking needs.'
        }
    ],
    'group': 'security',
    'weight': 20,
    'type': 'radio',
}

# version of Fuel when security group switch was added
RELEASE_VERSION = '9.0'


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()
    for release_name, env_version, cluster_name, node_id, uuid, mac in zip(
            ('release_1', 'release_2'),
            ('liberty-8.0', 'mitaka-9.0'),
            ('cluster_1', 'cluster_2'),
            (1, 2),
            ('fcd49872-3917-4a18-98f9-3f5acfe3fde',
             'fcd49872-3917-4a18-98f9-3f5acfe3fdd'),
            ('bb:aa:aa:aa:aa:aa', 'bb:aa:aa:aa:aa:cc')
    ):
        release = {
            'name': release_name,
            'version': env_version,
            'operating_system': 'ubuntu',
            'state': 'available',
            'networks_metadata': '{}',
            'attributes_metadata': jsonutils.dumps(ATTRIBUTES_METADATA),
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
        }
        result = db.execute(meta.tables['releases'].insert(), [release])
        release_id = result.inserted_primary_key[0]

        result = db.execute(
            meta.tables['clusters'].insert(),
            [{
                'name': cluster_name,
                'release_id': release_id,
                'mode': 'ha_compact',
                'status': 'new',
                'net_provider': 'neutron',
                'grouping': 'roles',
                'fuel_version': '9.0',
                'deployment_tasks': '{}'
            }])

        cluster_id = result.inserted_primary_key[0]
        editable = ATTRIBUTES_METADATA.get('editable', {})
        db.execute(
            meta.tables['attributes'].insert(),
            [{
                'cluster_id': cluster_id,
                'editable': jsonutils.dumps(editable)
            }]
        )
        db.execute(
            meta.tables['nodes'].insert(),
            [{
                'uuid': uuid,
                'cluster_id': cluster_id,
                'group_id': None,
                'status': 'ready',
                'roles': ['controller', 'ceph-osd'],
                'meta': '{}',
                'mac': mac,
                'timestamp': datetime.datetime.utcnow(),
            }]
        )
    db.commit()


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


class TestAttributesUpdate(base.BaseAlembicMigrationTest):

    def test_release_attributes_update(self):
        releases = self.meta.tables['releases']
        results = db.execute(
            sa.select([releases.c.attributes_metadata],
                      releases.c.id.in_(
                          self.get_release_ids(RELEASE_VERSION))))
        for attrs in results:
            attrs = jsonutils.loads(attrs[0])
            common = attrs.setdefault('editable', {}).setdefault('common', {})
            self.assertEqual(common.get('security_group'), SECURITY_GROUP)

    def test_release_attributes_no_update(self):
        releases = self.meta.tables['releases']
        results = db.execute(
            sa.select([releases.c.attributes_metadata],
                      releases.c.id.in_(
                          self.get_release_ids(RELEASE_VERSION,
                                               available=False))))
        for attrs in results:
            attrs = jsonutils.loads(attrs[0])
            common = attrs.setdefault('editable', {}).setdefault('common', {})
            self.assertEqual(common.get('security_group'), None)

    def test_cluster_attributes_update(self):
        clusters_attributes = self.meta.tables['attributes']
        clusters = self.meta.tables['clusters']
        releases_list = self.get_release_ids(RELEASE_VERSION)
        results = db.execute(
            sa.select([clusters_attributes.c.editable],
                      clusters.c.release_id.in_(releases_list)
                      ).select_from(sa.join(clusters, clusters_attributes,
                                            clusters.c.id ==
                                            clusters_attributes.c.cluster_id)))
        for editable in results:
            editable = jsonutils.loads(editable[0])
            common = editable.setdefault('common', {})
            self.assertEqual(common.get('security_group'), SECURITY_GROUP)

    def test_cluster_attributes_no_update(self):
        clusters_attributes = self.meta.tables['attributes']
        clusters = self.meta.tables['clusters']
        releases_list = self.get_release_ids(RELEASE_VERSION, available=False)
        results = db.execute(
            sa.select([clusters_attributes.c.editable],
                      clusters.c.release_id.in_(releases_list)
                      ).select_from(sa.join(clusters, clusters_attributes,
                                            clusters.c.id ==
                                            clusters_attributes.c.cluster_id)))
        for editable in results:
            editable = jsonutils.loads(editable[0])
            common = editable.setdefault('common', {})
            self.assertEqual(common.get('security_group'), None)

    def get_release_ids(self, start_version, available=True):
        """Get release ids

        :param start_version: String in version format "n.n"
               for comparing
        :param available: boolean value
        :return: * list of release ids since start_version
                 if available parameter is True
                 * list of release ids before start_version
                 if available parameter is False
        """
        releases = self.meta.tables['releases']
        results = db.execute(
            sa.select([releases.c.id,
                       releases.c.version]))
        release_ids = []
        for release_id, release_version in results:
            if (available ==
                    migration.is_security_group_available(release_version,
                                                          start_version)):
                release_ids.append(release_id)
        return release_ids
