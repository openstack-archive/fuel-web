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
from copy import deepcopy
import datetime
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '3763c404ca48'
_test_revision = 'f2314e5d63c9'


ATTRIBUTES_METADATA = {
    'editable': {
        'common': {}
    }
}
SECURITY_GROUPS = {
    'value': 'iptables_hybrid',
    'values': [
        {
            'data': 'openvswitch',
            'label': 'Open vSwitch Firewall Driver',
            'description': 'Choose this driver for OVS based security groups '
                           'implementation. NOTE: Open vSwitch Firewall '
                           'Driver requires kernel version >= 4.3 '
                           'for non-dpdk case.'
        },
        {
            'data': 'iptables_hybrid',
            'label': 'Iptables-based Firewall Driver'
                     ' (No firewall for DPDK case)',
            'description': 'Choose this driver for iptables/linux bridge '
                           'based security groups implementation.'
        }
    ],
    'group': 'security',
    'weight': 20,
    'type': 'radio',
}

ROLES_META = {
    'controller': {
        'tags': [
            'controller',
            'rabbitmq',
            'database',
            'keystone',
            'neutron'
        ]
    }
}

PLUGIN_ROLE_META = {
    'test_plugin_role': {
        'tags': ['test_plugin_tag']
    }
}

PLUGIN_TAGS_META = {
    'test_plugin_tag':
        {'has_primary': False}
}

TAGS_META = {
    'controller': {
        'has_primary': True,
    },
    'rabbitmq': {
        'has_primary': True
    },
    'database': {
        'has_primary': True
    },
    'keystone': {
        'has_primary': True
    },
    'neutron': {
        'has_primary': True
    }
}

NODE_ATTRIBUTES = {
    'hugepages':
        {
            'dpdk':
                {
                    'value': 0,
                    'min': 1024
                }
        }
}


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.downgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()

    attrs_with_sec_group = deepcopy(ATTRIBUTES_METADATA)
    attrs_with_sec_group.setdefault('editable', {}).setdefault(
        'common', {}).setdefault('security_group', SECURITY_GROUPS)
    plugin = {
        'name': 'Test_P',
        'version': '3.0.0',
        'title': 'Test Plugin',
        'package_version': '5.0.0',
        'roles_metadata': jsonutils.dumps(PLUGIN_ROLE_META),
        'tags_metadata': jsonutils.dumps(PLUGIN_TAGS_META)
    }
    result = db.execute(meta.tables['plugins'].insert(), [plugin])

    result = db.execute(
        meta.tables['releases'].insert(),
        [{
            'name': 'test_name',
            'version': 'mitaka-9.0',
            'operating_system': 'ubuntu',
            'state': 'available',
            'roles_metadata': jsonutils.dumps(ROLES_META),
            'tags_metadata': jsonutils.dumps(TAGS_META),
            'networks_metadata': jsonutils.dumps({
                'neutron': {
                    'networks': [],
                    'config': {}
                }
            }),
            'attributes_metadata': jsonutils.dumps(attrs_with_sec_group),
            'node_attributes': jsonutils.dumps(NODE_ATTRIBUTES),
        }])

    release_id = result.inserted_primary_key[0]

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
            'roles_metadata': jsonutils.dumps(ROLES_META),
            'tags_metadata': '{}',
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
            'primary_tags': ['controller', 'role_y'],
            'attributes': jsonutils.dumps(NODE_ATTRIBUTES),
            'meta': '{}',
            'mac': 'bb:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
        }]
    )

    editable = attrs_with_sec_group.get('editable', {})
    db.execute(
        meta.tables['attributes'].insert(),
        [{
            'cluster_id': result.inserted_primary_key[0],
            'editable': jsonutils.dumps(editable)
        }]
    )

    new_node = db.execute(
        meta.tables['nodes'].insert(),
        [{
            'uuid': '26b508d0-0d76-4159-bce9-f67ec2765481',
            'cluster_id': None,
            'group_id': None,
            'status': 'discover',
            'mac': 'aa:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
            'attributes': jsonutils.dumps(NODE_ATTRIBUTES),
        }]
    )
    node_id = new_node.inserted_primary_key[0]

    bond_interface = db.execute(
        meta.tables['node_bond_interfaces'].insert(),
        [{
            'node_id': node_id,
            'name': 'test_bond_interface',
            'mode': 'balance-tlb',
            'attributes': jsonutils.dumps({
                'lacp_rate': {'value': {'value': ''}},
                'xmit_hash_policy': {'value': {'value': 'layer2'}},
                'offloading': {
                    'disable': {'value': True},
                    'modes': {'value': {'tx-checksumming': None,
                                        'tx-checksum-sctp': None}}
                },
                'mtu': {'value': {'value': 50}},
                'lacp': {'value': {'value': ''}},
                'mode': {'value': {'value': 'balance-tlb'}},
                'type__': {'value': 'linux'},
                'dpdk': {'enabled': {'value': False}}
            })
        }]
    )
    bond_id = bond_interface.inserted_primary_key[0]

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
            'parent_id': bond_id,
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
                'dpdk': {'available': True}
            })
        }]
    )
    db.commit()


class TestTags(base.BaseAlembicMigrationTest):
    def test_primary_tags_downgrade(self):
        nodes = self.meta.tables['nodes']
        query = sa.select([nodes.c.primary_roles]).where(
            nodes.c.uuid == 'fcd49872-3917-4a18-98f9-3f5acfe3fdec')
        primary_roles = db.execute(query).fetchone()[0]
        self.assertItemsEqual(primary_roles, ['controller'])

    def test_downgrade_tags_metadata(self):
        releases = self.meta.tables['releases']
        self.assertNotIn('tags_metadata', releases.c._all_columns)

        clusters = self.meta.tables['clusters']
        self.assertNotIn('tags_metadata', clusters.c._all_columns)
        self.assertNotIn('roles_metadata', clusters.c._all_columns)

        plugins = self.meta.tables['plugins']
        self.assertNotIn('tags_metadata', plugins.c._all_columns)

    def test_downgrade_field_tags_from_roles(self):
        releases = self.meta.tables['releases']
        query = sa.select([releases.c.roles_metadata])
        for role_meta in db.execute(query).fetchall():
            self.assertNotIn('tags', role_meta)

        plugins = self.meta.tables['plugins']
        query = sa.select([plugins.c.roles_metadata])
        for role_meta in db.execute(query):
            self.assertNotIn('tags', role_meta)


class TestNodeNICAndBondAttributesMigration(base.BaseAlembicMigrationTest):

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
                       interfaces_table.c.offloading_modes,
                       interfaces_table.c.attributes,
                       interfaces_table.c.meta]).
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
                    'available': True
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

        self.assertEqual(result['meta'], '{}')
        self.assertEqual(result['attributes'], '{}')

    def test_downgrade_node_bond_attributes(self):
        node_bonds_table = self.meta.tables['node_bond_interfaces']
        result = db.execute(
            sa.select([node_bonds_table.c.interface_properties,
                       node_bonds_table.c.bond_properties,
                       node_bonds_table.c.offloading_modes,
                       node_bonds_table.c.attributes]).
            where(node_bonds_table.c.name == 'test_bond_interface')
        ).fetchone()

        self.assertEqual(
            jsonutils.loads(result['bond_properties']),
            {'type__': 'linux', 'mode': 'balance-tlb',
             'xmit_hash_policy': 'layer2'}
        )
        self.assertEqual(
            jsonutils.loads(result['interface_properties']),
            {'mtu': 50, 'disable_offloading': True,
             'dpdk': {'available': True, 'enabled': False}}
        )
        self.assertEqual(result['offloading_modes'], "[]")
        self.assertEqual(result['attributes'], "{}")


class TestAttributesDowngrade(base.BaseAlembicMigrationTest):

    def test_cluster_attributes_downgrade(self):
        clusters_attributes = self.meta.tables['attributes']
        results = db.execute(
            sa.select([clusters_attributes.c.editable]))
        for editable in results:
            editable = jsonutils.loads(editable[0])
            common = editable.setdefault('common', {})
            self.assertEqual(common.get('security_groups'), None)

    def test_release_attributes_downgrade(self):
        releases = self.meta.tables['releases']
        results = db.execute(
            sa.select([releases.c.attributes_metadata]))
        for attrs in results:
            attrs = jsonutils.loads(attrs[0])
            common = attrs.setdefault('editable', {}).setdefault('common', {})
            self.assertEqual(common.get('security_groups'), None)

    def test_release_node_attributes_downgrade(self):
        releases = self.meta.tables['releases']
        results = db.execute(
            sa.select([releases.c.node_attributes]))
        for node_attrs in results:
            node_attrs = jsonutils.loads(node_attrs[0])
            dpdk = node_attrs.setdefault('hugepages', {}).setdefault('dpdk',
                                                                     {})
            self.assertEqual(dpdk.get('min'), 0)
