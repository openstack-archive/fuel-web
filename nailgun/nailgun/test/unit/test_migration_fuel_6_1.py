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

from nailgun import consts
from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


_prepare_revision = '1b1d4016375d'
_test_revision = '37608259013'


def setup_module(module):
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
            'version': '2014.2-6.0',
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
        meta.tables['release_orchestrator_data'].insert(),
        [{
            'release_id': releaseid,
            'puppet_manifests_source': 'rsync://0.0.0.0:/puppet/manifests',
            'puppet_modules_source': 'rsync://0.0.0.0:/puppet/modules',
            'repo_metadata': jsonutils.dumps({
                'base': 'http://baseuri base-suite main',
                'test': 'http://testuri test-suite main',
            })
        }])

    result = db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test_env',
            'release_id': releaseid,
            'mode': 'ha_compact',
            'status': 'new',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '6.0',
        }])
    clusterid = result.inserted_primary_key[0]

    db.execute(
        meta.tables['attributes'].insert(),
        [{
            'cluster_id': clusterid,
            'editable': '{"common": {}}',
            'generated': '{"cobbler": {"profile": "ubuntu_1204_x86_64"}}',
        }])

    db.execute(
        meta.tables['ip_addrs'].insert(),
        [{
            'ip_addr': '192.168.0.2',
        }])

    db.execute(
        meta.tables['network_groups'].insert(),
        [{
            'name': 'public',
            'release': releaseid,
            'meta': jsonutils.dumps({'assign_vip': True})
        }])

    db.commit()


class TestVipTypesMigration(base.BaseAlembicMigrationTest):

    def test_vip_type_in_ip_addrs(self):
        ip_addrs_table = self.meta.tables['ip_addrs']
        self.assertIn('vip_type', ip_addrs_table.c)

        ip_addr = db.execute(
            sa.select([ip_addrs_table.c.vip_type]).where(
                ip_addrs_table.c.ip_addr == '192.168.0.2')
        ).first()
        self.assertEqual(ip_addr[0], consts.NETWORK_VIP_NAMES.haproxy)

    def test_vip_type_in_releases(self):
        releases_table = self.meta.tables['releases']

        networks_meta = jsonutils.loads(
            db.execute(
                sa.select([releases_table.c.networks_metadata])
            ).fetchone()[0]
        )
        neutron = networks_meta['neutron']['networks'][0]
        self.assertItemsEqual(
            neutron.get('vips'),
            [consts.NETWORK_VIP_NAMES.haproxy])

        nova_network = networks_meta['nova_network']['networks'][0]
        self.assertIsNone(nova_network.get('vips'))

    def test_default_vips_added_to_net_groups_meta(self):
        network_groups_table = self.meta.tables['network_groups']

        meta = db.execute(
            sa.select([network_groups_table.c.meta])
        ).first()[0]

        vips = jsonutils.loads(meta).get('vips')
        self.assertEqual(vips, [consts.NETWORK_VIP_NAMES.haproxy])


class TestRepoMetadataToRepoSetup(base.BaseAlembicMigrationTest):

    def test_release_orchestrator_data_table_is_removed(self):
        self.assertNotIn('release_orchestrator_data', self.meta.tables)

    def test_puppets_in_release_attributes(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.attributes_metadata]))
        attributes_metadata = jsonutils.loads(result.fetchone()[0])

        self.assertEqual(
            attributes_metadata['generated']['puppet'],
            {
                'manifests': 'rsync://0.0.0.0:/puppet/manifests',
                'modules': 'rsync://0.0.0.0:/puppet/modules',
            })

    def test_repo_setup_in_release_attributes(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.attributes_metadata]))
        attributes_metadata = jsonutils.loads(result.fetchone()[0])
        repo_setup = attributes_metadata['editable']['repo_setup']

        self.assertEqual(
            'custom_repo_configuration', repo_setup['repos']['type'])
        self.assertItemsEqual(
            repo_setup['repos']['value'],
            [
                {
                    'type': 'deb',
                    'name': 'base',
                    'uri': 'http://baseuri',
                    'suite': 'base-suite',
                    'section': 'main',
                    'priority': 1001,
                },
                {
                    'type': 'deb',
                    'name': 'test',
                    'uri': 'http://testuri',
                    'suite': 'test-suite',
                    'section': 'main',
                    'priority': 1001,
                },
            ])

    def test_puppets_in_cluster_attributes(self):
        result = db.execute(
            sa.select([self.meta.tables['attributes'].c.generated]))
        generated = jsonutils.loads(result.fetchone()[0])

        self.assertEqual(
            generated['puppet'],
            {
                'manifests': 'rsync://0.0.0.0:/puppet/manifests',
                'modules': 'rsync://0.0.0.0:/puppet/modules',
            })

    def test_repo_setup_in_cluster_attributes(self):
        result = db.execute(
            sa.select([self.meta.tables['attributes'].c.editable]))
        editable = jsonutils.loads(result.fetchone()[0])
        repo_setup = editable['repo_setup']

        self.assertEqual(
            repo_setup['metadata']['restrictions'], [{
                'condition': 'true',
                'action': 'hide',
            }])

        self.assertEqual(
            'custom_repo_configuration', repo_setup['repos']['type'])
        self.assertItemsEqual(
            repo_setup['repos']['value'],
            [
                {
                    'type': 'deb',
                    'name': 'base',
                    'uri': 'http://baseuri',
                    'suite': 'base-suite',
                    'section': 'main',
                    'priority': 1001,
                },
                {
                    'type': 'deb',
                    'name': 'test',
                    'uri': 'http://testuri',
                    'suite': 'test-suite',
                    'section': 'main',
                    'priority': 1001,
                },
            ])


class TestCobblerMigration(base.BaseAlembicMigrationTest):

    def test_cobbler_profile_updated(self):
        result = db.execute(
            sa.select([self.meta.tables['attributes'].c.generated]))
        generated = jsonutils.loads(result.fetchone()[0])
        self.assertEqual(generated['cobbler']['profile'], 'ubuntu_1404_x86_64')

        result = db.execute(sa.select(
            [self.meta.tables['releases'].c.attributes_metadata]))
        attrs_metadata = jsonutils.loads(result.fetchone()[0])
        self.assertEqual(
            attrs_metadata['generated']['cobbler']['profile']['generator_arg'],
            'ubuntu_1404_x86_64')


class TestRolesMetadataMigration(base.BaseAlembicMigrationTest):

    def test_mongo_has_primary(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.roles_metadata]))
        roles_metadata = jsonutils.loads(result.fetchone()[0])
        self.assertTrue(roles_metadata['mongo']['has_primary'])


class TestVmwareMigration(base.BaseAlembicMigrationTest):

    def test_use_vcenter_in_cluster_attributes(self):
        result = db.execute(
            sa.select([self.meta.tables['attributes'].c.editable]))
        editable = jsonutils.loads(result.fetchone()[0])
        self.assertEqual(
            editable['common']['use_vcenter'],
            {
                "value": False,
                "weight": 30,
                "type": "hidden"
            }
        )

    def test_use_vcenter_in_release_attributes_metadata(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.attributes_metadata]))
        attributes_metadata = jsonutils.loads(result.fetchone()[0])
        self.assertEqual(
            attributes_metadata['editable']['common']['use_vcenter'],
            {
                "value": False,
                "weight": 30,
                "type": "hidden"
            }
        )


class TestOldReleasesAreNotDeployable(base.BaseAlembicMigrationTest):

    def test_old_releases_are_not_deployable(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.is_deployable]))

        for row in result:
            self.assertFalse(row['is_deployable'])


class TestAddingModesToReleases(base.BaseAlembicMigrationTest):
    def test_release_modes_are_added(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.modes]))

        for row in result:
            self.assertItemsEqual(
                jsonutils.loads(row['modes']),
                ['ha_compact', 'multinode'])
