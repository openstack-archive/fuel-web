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

import alembic
import datetime
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


_prepare_revision = 'c6edea552f1e'
_test_revision = '675105097a69'


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
            'version': '2015.1-10.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'deployment_tasks': '{}',
            'roles': '{}',
            'roles_metadata': '{}',
            'is_deployable': True,
            'required_component_types': ['network', 'storage']
        }]
    )

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
        }]
    )
    cluster_id = result.inserted_primary_key[0]

    TestPluginLinksConstraints.prepare(meta, cluster_id)
    TestNodeNICAttributesMigration.prepare(meta)


class TestPluginLinksConstraints(base.BaseAlembicMigrationTest):
    test_link = {
        'title': 'title',
        'url': 'http://www.zzz.com',
        'description': 'description',
        'hidden': False
    }

    @classmethod
    def prepare(cls, meta, cluster_id):
        cls.test_link['cluster_id'] = cluster_id

        db.execute(
            meta.tables['cluster_plugin_links'].insert(),
            [cls.test_link],
        )

    def test_duplicate_cluster_link(self):
        db.execute(
            self.meta.tables['cluster_plugin_links'].insert(),
            [self.test_link]
        )

        links_count = db.execute(
            sa.select(
                [sa.func.count(self.meta.tables['cluster_plugin_links'].c.id)]
            )).fetchone()[0]
        self.assertEqual(links_count, 2)


class TestRequiredComponentTypesField(base.BaseAlembicMigrationTest):

    def test_downgrade_release_required_component_types(self):
        releases_table = self.meta.tables['releases']
        self.assertNotIn('required_component_types', releases_table.c)


class TestNodeNICAttributesMigration(base.BaseAlembicMigrationTest):
    @classmethod
    def prepare(cls, meta):
        new_node = db.execute(
            meta.tables['nodes'].insert(),
            [{
                'uuid': '26b508d0-0d76-4159-bce9-f67ec2765481',
                'cluster_id': None,
                'group_id': None,
                'status': 'discover',
                'mac': 'aa:aa:aa:aa:aa:aa',
                'timestamp': datetime.datetime.utcnow()
            }]
        )
        node_id = new_node.inserted_primary_key[0]

        db.execute(
            meta.tables['node_nic_interfaces'].insert(),
            [{
                'node_id': node_id,
                'name': 'test_nic_empty_attributes',
                'mac': '00:00:00:00:00:01',
                'attributes': jsonutils.dumps({}),
                'meta': jsonutils.dumps({})
            }]
        )
        db.execute(
            meta.tables['node_nic_interfaces'].insert(),
            [{
                'node_id': node_id,
                'name': 'test_nic_attributes',
                'mac': '00:00:00:00:00:01',
                'attributes': jsonutils.dumps({
                    'offloading': {
                        'disable': {'value': 'test_disable_offloading'},
                        'modes': {
                            'value': {
                                'tx-checksum-ipv4': 'IPV4_STATE',
                                'tx-checksumming': 'TX_STATE',
                                'rx-checksumming': 'RX_STATE',
                                'tx-checksum-ipv6': 'IPV6_STATE'
                            }
                        }
                    },
                    'mtu': {
                        'value': {'value': 'test_mtu'}
                    },
                    'sriov': {
                        'numvfs': {'value': 'test_sriov_numfs'},
                        'enabled': {'value': 'test_sriov_enabled'},
                        'physnet': {'value': 'test_sriov_physnet'}
                    },
                    'dpdk': {
                        'enabled': {'value': 'test_dpdk_enabled'}
                    }
                }),
                'meta': jsonutils.dumps({
                    'offloading_modes': [{
                        'state': None,
                        'name': 'tx-checksumming',
                        'sub': [
                            {'state': False, 'name': 'tx-checksum-sctp',
                             'sub': []},
                            {'state': None, 'name': 'tx-checksum-ipv6',
                             'sub': []},
                            {'state': None, 'name': 'tx-checksum-ipv4',
                             'sub': []}
                        ]
                    }, {
                        'state': None, 'name': 'rx-checksumming', 'sub': []
                    }],
                    'numa_node': 12345,
                    'pci_id': 'test_pci_id',
                    'sriov': {
                        'available': 'test_sriov_available',
                        'totalvfs': 6789,
                        'pci_id': 'test_sriov_pci_id'
                    },
                    'dpdk': {'available': 'test_dpdk_availiable'}
                })
            }]
        )

    def test_downgrade_release_with_nic_attributes(self):
        releases_table = self.meta.tables['releases']
        self.assertNotIn('nic_attributes', releases_table.c)
        self.assertNotIn('bond_attributes', releases_table.c)

    def test_downgrade_node_nic_attributes_with_empty_attributes(self):
        interfaces_table = self.meta.tables['node_nic_interfaces']
        result = db.execute(
            sa.select([interfaces_table.c.interface_properties,
                       interfaces_table.c.offloading_modes]).
            where(interfaces_table.c.name == 'test_nic_empty_attributes')
        ).fetchone()
        self.assertEqual(
            jsonutils.loads(result['interface_properties']),
            {
                'mtu': None,
                'disable_offloading': False,
                'sriov': {
                    'enabled': False,
                    'available': False,
                    'sriov_numvfs': None,
                    'physnet': 'physnet2',
                    'pci_id': '',
                    'sriov_totalvfs': 0
                },
                'dpdk': {
                    'enabled': False,
                    'available': False
                }
            }
        )
        self.assertEqual(jsonutils.loads(result['offloading_modes']), [])

    def test_downgrade_node_nic_attributes(self):
        interfaces_table = self.meta.tables['node_nic_interfaces']
        result = db.execute(
            sa.select([interfaces_table.c.interface_properties,
                       interfaces_table.c.offloading_modes]).
            where(interfaces_table.c.name == 'test_nic_attributes')
        ).fetchone()

        self.assertEqual(
            jsonutils.loads(result['interface_properties']),
            {
                'mtu': 'test_mtu',
                'disable_offloading': 'test_disable_offloading',
                'sriov': {
                    'enabled': 'test_sriov_enabled',
                    'available': 'test_sriov_available',
                    'sriov_numvfs': 'test_sriov_numfs',
                    'physnet': 'test_sriov_physnet',
                    'pci_id': 'test_sriov_pci_id',
                    'sriov_totalvfs': 6789
                },
                'dpdk': {
                    'enabled': 'test_dpdk_enabled',
                    'available': 'test_dpdk_availiable'
                }
            }
        )
        self.assertEqual(
            jsonutils.loads(result['offloading_modes']),
            [{
                'state': 'TX_STATE',
                'name': 'tx-checksumming',
                'sub': [
                    {'state': False, 'name': 'tx-checksum-sctp', 'sub': []},
                    {'state': 'IPV6_STATE', 'name': 'tx-checksum-ipv6',
                     'sub': []},
                    {'state': 'IPV4_STATE', 'name': 'tx-checksum-ipv4',
                     'sub': []}
                ]
            }, {
                'state': 'RX_STATE', 'name': 'rx-checksumming', 'sub': []
            }]
        )

    def test_downgrade_node_nic_attributes_fields(self):
        interfaces_table = self.meta.tables['node_nic_interfaces']
        self.assertNotIn('meta', interfaces_table.c)
        self.assertNotIn('attributes', interfaces_table.c)
        self.assertIn('interface_properties', interfaces_table.c)
