#    Copyright 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the 'License'); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import alembic
from copy import deepcopy
from distutils import version
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun import consts
from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun import objects
from nailgun.test import base


_prepare_revision = 'c6edea552f1e'
_test_revision = 'de475d3a79d6'

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
                           ' use OVS Brige for networking needs.'
        },
        {
            'data': 'iptables_hybrid',
            'label': 'Iptables-based Firewall Driver',
            'description': 'Choose this type of firewall driver if you'
                           ' use Linux Bridge for networking needs.'
        }
    ],
    'group': 'security',
    'weight': 20,
    'type': 'radio',
}


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    release_ids = []
    cluster_ids = []
    meta = base.reflect_db_metadata()
    for name, env_version in zip(['release_1', 'release_2', 'release_3'],
                                 ['mitaka-9.0', 'mitaka-9.0', 'liberty-8.0']):
        attrs = deepcopy(ATTRIBUTES_METADATA)
        if name == 'release_1':
            attrs['editable']['common']['security_group'] = SECURITY_GROUP
        result = db.execute(
            meta.tables['releases'].insert(),
            [{
                'name': name,
                'version': env_version,
                'operating_system': 'ubuntu',
                'state': 'available',
                'deployment_tasks': '[]',
                'roles': '[]',
                'roles_metadata': '{}',
                'is_deployable': True,
                'networks_metadata': '{}',
                'attributes_metadata': jsonutils.dumps(attrs)
            }]
        )
        release_ids.append(result.inserted_primary_key[0])

    for cluster_name, release_id in zip(['cluster_1', 'cluster_2',
                                         'cluster_3'], release_ids):
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
                'deployment_tasks': '[]',
            }])
        cluster_ids.append(result.inserted_primary_key[0])

    for cluster_id in cluster_ids:
        editable = deepcopy(ATTRIBUTES_METADATA.get('editable'))
        if cluster_id == 1:
            editable['common']['security_group'] = SECURITY_GROUP
        db.execute(
            meta.tables['attributes'].insert(),
            [{
                'cluster_id': cluster_id,
                'editable': jsonutils.dumps(editable)
            }]
        )
    db.commit()


class TestAttributesUpdate(base.BaseAlembicMigrationTest):

    def test_cluster_attributes_update(self):
        clusters_attributes = self.meta.tables['attributes']
        results = db.execute(
            sa.select([clusters_attributes.c.id,
                       clusters_attributes.c.editable])).fetchall()
        for id, editable in results:
            editable = jsonutils.loads(editable)
            env_version = \
                objects.Cluster.get_by_uid(id).release.environment_version
            if self._is_available_version_for_security_group(env_version):
                self.assertEqual(
                    editable['common']['security_group'], SECURITY_GROUP)
            else:
                self.assertEqual(
                    editable['common'].get('security_group'), None)

    def test_release_attributes_update(self):
        releases = self.meta.tables['releases']
        results = db.execute(
            sa.select([releases.c.id,
                       releases.c.attributes_metadata])).fetchall()
        for id, attrs in results:
            attrs = jsonutils.loads(attrs)
            env_version = \
                objects.Release.get_by_uid(id).environment_version
            if self._is_available_version_for_security_group(env_version):
                self.assertEqual(
                    attrs['editable']['common']['security_group'],
                    SECURITY_GROUP)
            else:
                self.assertEqual(
                    attrs['editable']['common'].get('security_group'), None)

    @staticmethod
    def _is_available_version_for_security_group(env_version):
        if version.StrictVersion(env_version) < version.StrictVersion(
                consts.FUEL_SECURITY_GROUP_AVAILABLE_SINCE):
            return False
        return True
