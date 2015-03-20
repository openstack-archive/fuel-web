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


from oslo.serialization import jsonutils
import sqlalchemy as sa

from nailgun import consts
from nailgun.db import db
from nailgun.test import base


class TestRepoMetadataToRepoSetup(base.BaseAlembicMigrationTest):

    prepare_revision = '1b1d4016375d'
    test_revision = '37608259013'

    @classmethod
    def prepare(cls):
        meta = sa.MetaData()
        meta.reflect(bind=db.get_bind())

        result = db.execute(
            meta.tables['releases'].insert(),
            [{
                'name': 'test_name',
                'version': '2014.2-6.0',
                'operating_system': 'ubuntu',
                'state': 'available',
                'roles_metadata': jsonutils.dumps({}),
                'attributes_metadata': jsonutils.dumps({
                    'editable': {
                        'storage': {
                            'volumes_lvm': {},
                        }
                    },
                    'generated': {},
                }),
                'networks_metadata': '{}',
                'is_deployable': True,
            }])
        releaseid = result.inserted_primary_key[0]

        db.execute(
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
                'editable': '{}',
                'generated': '{}',
            }])

        cls.ip_addr_to_check = '192.168.0.2'
        db.execute(
            meta.tables['ip_addrs'].insert(),
            [{
                'ip_addr': cls.ip_addr_to_check,
            }])

        db.commit()

    def test_vip_type_in_ip_addrs(self):
        meta = sa.MetaData()
        meta.reflect(bind=db.get_bind())
        self.assertIn('vip_type', meta.tables['ip_addrs'].c)

        ip_addrs_table = meta.tables['ip_addrs']
        ip_addr = db.execute(
            sa.select([ip_addrs_table.c.vip_type]).where(
                ip_addrs_table.c.ip_addr == self.ip_addr_to_check)
        ).first()
        self.assertEqual(ip_addr[0], consts.NETWORK_VIP_TYPES.haproxy)

    def test_release_orchestrator_data_table_is_removed(self):
        meta = sa.MetaData()
        meta.reflect(bind=db.get_bind())

        self.assertNotIn('release_orchestrator_data', meta.tables)

    def test_puppets_in_release_attributes(self):
        meta = sa.MetaData()
        meta.reflect(bind=db.get_bind())

        result = db.execute(
            sa.select([meta.tables['releases'].c.attributes_metadata]))
        attributes_metadata = jsonutils.loads(result.fetchone()[0])

        self.assertEqual(
            attributes_metadata['generated']['puppet'],
            {
                'manifests': 'rsync://0.0.0.0:/puppet/manifests',
                'modules': 'rsync://0.0.0.0:/puppet/modules',
            })

    def test_repo_setup_in_release_attributes(self):
        meta = sa.MetaData()
        meta.reflect(bind=db.get_bind())

        result = db.execute(
            sa.select([meta.tables['releases'].c.attributes_metadata]))
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
        meta = sa.MetaData()
        meta.reflect(bind=db.get_bind())

        result = db.execute(sa.select([meta.tables['attributes'].c.generated]))
        generated = jsonutils.loads(result.fetchone()[0])

        self.assertEqual(
            generated['puppet'],
            {
                'manifests': 'rsync://0.0.0.0:/puppet/manifests',
                'modules': 'rsync://0.0.0.0:/puppet/modules',
            })

    def test_repo_setup_in_cluster_attributes(self):
        meta = sa.MetaData()
        meta.reflect(bind=db.get_bind())

        result = db.execute(sa.select([meta.tables['attributes'].c.editable]))
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
