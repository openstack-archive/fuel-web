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
from oslo.serialization import jsonutils
import six
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


_prepare_revision = '37608259013'
_test_revision = '1e50a4903910'

_RELEASE = {
    'name': 'test_name',
    'version': '2015.2-7.0',
    'operating_system': 'ubuntu',
    'state': 'available',
    'roles_metadata': jsonutils.dumps({
        "primary-controller": {
            "name": "Primary Controller",
            "description": "Primary Controller role"
        },
        "controller": {
            "name": "Controller",
            "description": "Controller role"
        },
        "zabbix-server": {
            "name": "Zabbix Server",
            "description": "Zabbix Server role"
        },
        "cinder": {
            "name": "Cinder",
            "description": "Cinder role"
        }
    }),
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
        }

    }),
    'is_deployable': True,
}


def setup_module(module):
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()

    db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin',
            'title': 'Test plugin',
            'version': '1.0.0',
            'description': 'Test plugin for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '3.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['6.1', '7.0']),
        }])

    db.execute(meta.tables['releases'].insert(), [_RELEASE])

    db.commit()


class TestPluginAttributesMigration(base.BaseAlembicMigrationTest):

    def test_old_fields_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.name]))
        self.assertEqual(
            result.fetchone()[0], 'test_plugin')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.title]))
        self.assertEqual(
            result.fetchone()[0], 'Test plugin')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.version]))
        self.assertEqual(
            result.fetchone()[0], '1.0.0')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.description]))
        self.assertEqual(
            result.fetchone()[0], 'Test plugin for Fuel')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.homepage]))
        self.assertEqual(
            result.fetchone()[0], 'http://fuel_plugins.test_plugin.com')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.package_version]))
        self.assertEqual(
            result.fetchone()[0], '3.0.0')

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.groups]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), ['tgroup'])

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.authors]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), ['tauthor'])

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.licenses]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), ['tlicense'])

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.releases]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]),
            [{'repository_path': 'repositories/ubuntu'}])

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.fuel_version]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), ['6.1', '7.0'])

    def test_new_fields_exists_and_empty(self):
        # check attributes_metadata field exists
        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.attributes_metadata]))
        # check attributes_metadata value is empty
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), {})

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.volumes_metadata]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), {})

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.roles_metadata]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), {})

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.deployment_tasks]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), [])

        result = db.execute(
            sa.select([self.meta.tables['plugins'].c.tasks]))
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), [])


class TestReleaseNetworkRolesMetadataMigration(base.BaseAlembicMigrationTest):
    def test_old_fields_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.name]))
        self.assertEqual(
            result.fetchone()[0], _RELEASE['name'])

        result = db.execute(
            sa.select([self.meta.tables['releases'].c.operating_system]))
        self.assertEqual(
            result.fetchone()[0], _RELEASE['operating_system'])

        result = db.execute(
            sa.select([self.meta.tables['releases'].c.state]))
        self.assertEqual(
            result.fetchone()[0], _RELEASE['state'])

        result = db.execute(
            sa.select([self.meta.tables['releases'].c.attributes_metadata]))
        self.assertEqual(
            result.fetchone()[0], _RELEASE['attributes_metadata'])

        result = db.execute(
            sa.select([self.meta.tables['releases'].c.networks_metadata]))
        self.assertEqual(
            result.fetchone()[0], _RELEASE['networks_metadata'])

        result = db.execute(
            sa.select([self.meta.tables['releases'].c.is_deployable]))
        self.assertEqual(
            result.fetchone()[0], _RELEASE['is_deployable'])

    def test_new_fields_exists_and_empty(self):
        # check attributes_metadata field exists
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.network_roles_metadata]))
        # check attributes_metadata value is empty
        self.assertEqual(
            jsonutils.loads(result.fetchone()[0]), {})

    def test_releases_roles_metadata(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.roles_metadata]))
        roles_metadata = jsonutils.loads(result.fetchone()[0])
        for role, role_info in six.iteritems(roles_metadata):
            if role in ['controller', 'zabbix-server']:
                self.assertTrue(role_info['public_ip_required'])
            else:
                self.assertFalse(role_info.get('public_ip_required'))
