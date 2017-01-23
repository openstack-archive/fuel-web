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

import copy
import datetime

import alembic
from oslo_serialization import jsonutils
import six
import sqlalchemy as sa

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base
from nailgun.utils import is_feature_supported
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

DEFAULT_NIC_ATTRIBUTES = {
    'offloading': {
        'disable': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'Disable Offloading'},
        'modes': {'value': {}, 'type': 'offloading_modes', 'weight': 20,
                  'label': 'Offloading Modes'},
        'metadata': {'weight': 10, 'label': 'Offloading'}
    },
    'mtu': {
        'value': {'type': 'number', 'value': None, 'weight': 10,
                  'label': 'Use Custom MTU', 'nullable': True,
                  'min': 42, 'max': 65536},
        'metadata': {'weight': 20, 'label': 'MTU'}
    },
    'sriov': {
        'numvfs': {'min': 1, 'type': 'number', 'value': None, 'nullable': True,
                   'weight': 20, 'label': 'Custom Number of Virtual Functions',
                   'restrictions': ['nic_attributes:sriov.enabled.value == "'
                                    'false"']
                   },
        'enabled': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'Enable SR-IOV',
                    'description': 'Single-root I/O Virtualization (SR-IOV) '
                                   'is a specification that, when implemented '
                                   'by a physical PCIe device, enables it to '
                                   'appear as multiple separate PCIe devices. '
                                   'This enables multiple virtualized guests '
                                   'to share direct access to the physical '
                                   'device, offering improved performance '
                                   'over an equivalent virtual device.',
                    'restrictions': [{'settings:common.libvirt_type.value != '
                                      '\'kvm\'': '"Only KVM hypervisor works '
                                      'with SR-IOV"'}]},
        'physnet': {'type': 'text', 'value': '', 'weight': 30,
                    'label': 'Physical Network Name',
                    'regex': {
                        'source': '^[A-Za-z0-9 _]*[A-Za-z0-9][A-Za-z0-9 _]*$',
                        'error': 'Invalid physical network name'
                    },
                    'restrictions': [
                        'nic_attributes:sriov.enabled.value == false',
                        {'condition': "nic_attributes:sriov.physnet.value "
                                      "!= 'physnet2'",
                         'message': 'Only "physnet2" will be configured by '
                                    'Fuel in Neutron. Configuration of other '
                                    'physical networks is up to Operator or '
                                    'plugin. Fuel will just configure '
                                    'appropriate pci_passthrough_whitelist '
                                    'option in nova.conf for such interface '
                                    'and physical networks.',
                         'action': 'none'
                         }
                    ]},
        'metadata': {'weight': 30, 'label': 'SR-IOV'}
    },
    'dpdk': {
        'enabled': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'Enable DPDK',
                    'description': 'The Data Plane Development Kit (DPDK) '
                                   'provides high-performance packet '
                                   'processing libraries and user space '
                                   'drivers.',
                    'restrictions': [
                        {'settings:common.libvirt_type.value != \'kvm\'':
                         'Only KVM hypervisor works with DPDK'}
                    ]},
        'metadata': {
            'weight': 40, 'label': 'DPDK',
            'restrictions': [{
                'condition': "not ('experimental' in version:feature_groups)",
                'action': "hide"
            }]
        }
    }
}

DEFAULT_BOND_ATTRIBUTES = {
    'lacp_rate': {
        'value': {'type': 'select', 'weight': 10, 'value': '',
                  'label': 'Lacp rate'},
        'metadata': {'weight': 60, 'label': 'Lacp rate'}
    },
    'xmit_hash_policy': {
        'value': {'type': 'select', 'weight': 10, 'value': '',
                  'label': 'Xmit hash policy'},
        'metadata': {'weight': 70, 'label': 'Xmit hash policy'}
    },
    'offloading': {
        'disable': {'type': 'checkbox', 'weight': 10, 'value': False,
                    'label': 'Disable Offloading'},
        'modes': {'weight': 20, 'type': 'offloading_modes',
                  'value': {}, 'label': 'Offloading Modes'},
        'metadata': {'weight': 20, 'label': 'Offloading'}
    },
    'mtu': {
        'value': {'type': 'number', 'weight': 10, 'value': None,
                  'label': 'Use Custom MTU', 'nullable': True,
                  'min': 42, 'max': 65536},
        'metadata': {'weight': 30, 'label': 'MTU'}
    },
    'lacp': {
        'value': {'type': 'select', 'weight': 10, 'value': '',
                  'label': 'Lacp'},
        'metadata': {'weight': 50, 'label': 'Lacp'}
    },
    'mode': {
        'value': {'type': 'select', 'weight': 10, 'value': '',
                  'label': 'Mode'},
        'metadata': {'weight': 10, 'label': 'Mode'}
    },
    'type__': {'type': 'hidden', 'value': None},
    'dpdk': {
        'enabled': {'type': 'checkbox', 'value': False,
                    'weight': 10, 'label': 'Enable DPDK',
                    'description': 'The Data Plane Development Kit (DPDK) '
                                   'provides high-performance packet '
                                   'processing libraries and user space '
                                   'drivers.',
                    'restrictions': [
                        {'settings:common.libvirt_type.value != \'kvm\'':
                         'Only KVM hypervisor works with DPDK'}
                    ]},
        'metadata': {
            'weight': 40, 'label': 'DPDK',
            'restrictions': [{
                'condition': "not ('experimental' in version:feature_groups)",
                'action': "hide"
            }]
        }
    }
}

NODE_NIC_PROPERTIES = {
    'mtu': 'test_mtu',
    'disable_offloading': 'test_disable_offloading',
    'sriov': {
        'available': 'test_sriov_available',
        'sriov_numvfs': 'test_sriov_sriov_numvfs',
        'enabled': 'test_sriov_enabled',
        'pci_id': 'test_sriov_pci_id',
        'sriov_totalvfs': 'test_sriov_totalvfs',
        'physnet': 'test_sriov_physnet'
    },
    'dpdk': {
        'available': 'test_dpdk_available',
        'enabled': 'test_dpdk_enabled',
    },
    'pci_id': 'test_pci_id',
    'numa_node': 12345
}

NODE_OFFLOADING_MODES = [
    {
        'state': True,
        'name': 'tx-checksumming',
        'sub': [{
            'state': True,
            'name': 'tx-checksum-sctp',
            'sub': []
        }, {
            'state': False,
            'name': 'tx-checksum-ipv6',
            'sub': []
        }]
    }, {
        'state': None,
        'name': 'rx-checksumming',
        'sub': []
    }, {
        'state': None,
        'name': 'rx-vlan-offload',
        'sub': []
    }
]
# version of Fuel when security group switch was added
RELEASE_VERSION = '9.0'
# version of Fuel when tags was introduced
FUEL_TAGS_SUPPORT = '9.0'

NEW_ROLES_META = {
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

NEW_TAGS_LIST = [
    'rabbitmq',
    'database',
    'keystone',
    'neutron'
]


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    meta = base.reflect_db_metadata()
    for release_name, env_version, cluster_name, uuid, mac in zip(
            ('release_1', 'release_2'),
            ('liberty-8.0', 'mitaka-9.0'),
            ('cluster_1', 'cluster_2'),
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
                'primary_roles': ['controller'],
                'meta': jsonutils.dumps({
                    'interfaces': [{
                        'mac': '00:00:00:00:00:01'
                    }]
                }),
                'mac': mac,
                'timestamp': datetime.datetime.utcnow(),
            }]
        )

    node_interface_properties = copy.deepcopy(NODE_NIC_PROPERTIES)
    node_interface_properties['dpdk'].pop('available')
    result = db.execute(
        meta.tables['nodes'].insert(),
        [{
            'uuid': 'fcd49872-3917-4a18-98f9-3f5acfe3fdec',
            'cluster_id': cluster_id,
            'group_id': None,
            'status': 'ready',
            'roles': ['controller', 'ceph-osd'],
            'meta': jsonutils.dumps({
                'interfaces': [
                    {
                        'name': 'test_nic_empty_attributes',
                        'mac': '00:00:00:00:00:01',
                        'interface_properties': {}
                    },
                    {
                        'name': 'test_nic_attributes',
                        'mac': '00:00:00:00:00:02',
                        'interface_properties': node_interface_properties,
                        'offloading_modes': NODE_OFFLOADING_MODES
                    },
                    {
                        'name': 'test_nic_attributes_2',
                        'mac': '00:00:00:00:00:03',
                        'interface_properties': node_interface_properties,
                        'offloading_modes': [
                            {
                                'state': True,
                                'name': 'tx-checksumming',
                                'sub': [{
                                    'state': False,
                                    'name': 'tx-checksum-sctp',
                                    'sub': []
                                }]
                            }, {
                                'state': True,
                                'name': 'rx-checksumming',
                                'sub': []
                            }, {
                                'state': False,
                                'name': 'rx-vlan-offload',
                                'sub': []
                            }
                        ]
                    }
                ]
            }),
            'mac': 'bb:bb:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
            'hostname': 'test_node'
        }]
    )
    node_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['node_bond_interfaces'].insert(),
        [{
            'node_id': node_id,
            'name': 'test_bond_interface',
            'mode': 'active-backup',
            'bond_properties': jsonutils.dumps(
                {'test_property': 'test_value'})
        }]
    )

    bond = db.execute(
        meta.tables['node_bond_interfaces'].insert(),
        [{
            'node_id': node_id,
            'name': 'test_bond_interface_attributes',
            'mode': '802.3ad',
            'bond_properties': jsonutils.dumps(
                {'lacp_rate': 'slow', 'type__': 'linux',
                 'mode': '802.3ad', 'xmit_hash_policy': 'layer2'}),
            'interface_properties': jsonutils.dumps(
                {'mtu': 2000, 'disable_offloading': False,
                 'dpdk': {'available': True, 'enabled': True}})
        }]
    )
    bond_id = bond.inserted_primary_key[0]

    db.execute(
        meta.tables['node_nic_interfaces'].insert(),
        [{
            'node_id': node_id,
            'name': 'test_nic_empty_attributes',
            'mac': '00:00:00:00:00:01',
            'interface_properties': "{}",
            'offloading_modes': "[]"
        }]
    )

    changed_offloading_modes = copy.deepcopy(NODE_OFFLOADING_MODES)
    changed_offloading_modes[0]['state'] = False
    db.execute(
        meta.tables['node_nic_interfaces'].insert(),
        [{
            'node_id': node_id,
            'parent_id': bond_id,
            'name': 'test_nic_attributes',
            'mac': '00:00:00:00:00:02',
            'interface_properties': jsonutils.dumps(NODE_NIC_PROPERTIES),
            'offloading_modes': jsonutils.dumps(changed_offloading_modes)
        }]
    )

    db.execute(
        meta.tables['node_nic_interfaces'].insert(),
        [{
            'node_id': node_id,
            'parent_id': bond_id,
            'name': 'test_nic_attributes_2',
            'mac': '00:00:00:00:00:03',
            'interface_properties': jsonutils.dumps(NODE_NIC_PROPERTIES),
            'offloading_modes': jsonutils.dumps([
                {
                    'state': True,
                    'name': 'tx-checksumming',
                    'sub': [{
                        'state': True,
                        'name': 'tx-checksum-sctp',
                        'sub': []
                    }]
                }, {
                    'state': True,
                    'name': 'rx-checksumming',
                    'sub': []
                }, {
                    'state': False,
                    'name': 'rx-vlan-offload',
                    'sub': []
                }
            ])
        }]
    )

    db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_tags',
            'title': 'Test tags plugin',
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
            'deployment_tasks': jsonutils.dumps([]),
            'fuel_version': jsonutils.dumps(['9.2']),
            'network_roles_metadata': jsonutils.dumps([]),
            'roles_metadata': jsonutils.dumps({
                'plugin-tags-controller': {
                    'name': 'Plugin Tags Controller',
                },
            }),
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
            self.assertEqual(common.get('security_groups'), SECURITY_GROUPS)

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
            self.assertIsNone(common.get('security_groups'))

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
            self.assertEqual(common.get('security_groups'), SECURITY_GROUPS)

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
            self.assertIsNone(common.get('security_groups'))

    def test_upgrade_release_with_nic_attributes(self):
        releases_table = self.meta.tables['releases']
        result = db.execute(
            sa.select([releases_table.c.nic_attributes,
                       releases_table.c.bond_attributes],
                      releases_table.c.id.in_(
                          self.get_release_ids(RELEASE_VERSION)))
        ).fetchone()
        self.assertEqual(DEFAULT_NIC_ATTRIBUTES,
                         jsonutils.loads(result['nic_attributes']))
        self.assertEqual(DEFAULT_BOND_ATTRIBUTES,
                         jsonutils.loads(result['bond_attributes']))

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
                    migration.is_security_groups_available(release_version,
                                                           start_version)):
                release_ids.append(release_id)
        return release_ids


class TestTags(base.BaseAlembicMigrationTest):
    def test_primary_tags_migration(self):
        nodes = self.meta.tables['nodes']
        query = sa.select([nodes.c.primary_tags]).where(
            nodes.c.uuid == 'fcd49872-3917-4a18-98f9-3f5acfe3fde')
        primary_tags = db.execute(query).fetchone()[0]
        self.assertItemsEqual(primary_tags, ['controller'])

    def test_tags_releases_meta_migration(self):
        releases = self.meta.tables['releases']
        query = sa.select([releases.c.roles_metadata,
                           releases.c.tags_metadata])
        for roles_meta, tags_meta in db.execute(query):
            tags_meta = jsonutils.loads(tags_meta)
            for role_name, role_meta in six.iteritems(
                    jsonutils.loads(roles_meta)):
                self.assertEqual(
                    tags_meta[role_name].get('has_primary', False),
                    role_meta.get('has_primary', False)
                )
                self.assertIn('tags', role_meta)

    def test_tags_plugins_meta_migration(self):
        plugins = self.meta.tables['plugins']
        query = sa.select([plugins.c.roles_metadata,
                           plugins.c.tags_metadata])
        for roles_meta, tags_meta in db.execute(query):
            tags_meta = jsonutils.loads(tags_meta)
            for role_name, role_meta in six.iteritems(
                    jsonutils.loads(roles_meta)):
                self.assertEqual(
                    tags_meta[role_name].get('has_primary', False),
                    role_meta.get('has_primary', False)
                )
                self.assertIn('tags', role_meta)

    def test_tags_migration_for_supported_releases(self):
        releases = self.meta.tables['releases']
        query = sa.select([releases.c.version,
                           releases.c.roles_metadata,
                           releases.c.tags_metadata])
        for version, roles_meta, tags_meta in db.execute(query):

            if not is_feature_supported(version, FUEL_TAGS_SUPPORT):
                continue

            roles_meta = jsonutils.loads(roles_meta)
            for role_name, role_meta in six.iteritems(NEW_ROLES_META):
                self.assertItemsEqual(
                    roles_meta[role_name]['tags'],
                    role_meta['tags']
                )
            tags_meta = jsonutils.loads(tags_meta)
            missing_tags = set(NEW_TAGS_LIST) - set(tags_meta)
            self.assertEqual(len(missing_tags), 0)

    def test_tags_migration_for_not_supported_releases(self):
        releases = self.meta.tables['releases']
        query = sa.select([releases.c.version,
                           releases.c.roles_metadata,
                           releases.c.tags_metadata])
        for version, roles_meta, tags_meta in db.execute(query):

            if is_feature_supported(version, FUEL_TAGS_SUPPORT):
                continue

            roles_meta = jsonutils.loads(roles_meta)
            for role_name, role_meta in six.iteritems(NEW_ROLES_META):
                common_tags = (set(role_meta['tags']) &
                               set(roles_meta[role_name]['tags']))
                # common tag 'controller' for backward compatibility
                self.assertEqual(len(common_tags), 1)
            tags_meta = jsonutils.loads(tags_meta)
            wrong_tags = set(NEW_TAGS_LIST) - set(tags_meta)
            self.assertNotEqual(len(wrong_tags), 0)


class TestNodeNICAndBondAttributesMigration(base.BaseAlembicMigrationTest):

    def test_upgrade_node_nic_attributes_with_empty_properties(self):
        interfaces_table = self.meta.tables['node_nic_interfaces']
        result = db.execute(
            sa.select([interfaces_table.c.meta,
                       interfaces_table.c.attributes]).
            where(interfaces_table.c.name == 'test_nic_empty_attributes')
        ).fetchone()

        self.assertEqual(jsonutils.loads(result['meta']),
                         {'offloading_modes': [],
                          'sriov': {'available': False,
                                    'pci_id': '', 'totalvfs': 0},
                          'dpdk': {'available': False},
                          'pci_id': '',
                          'numa_node': None})

        expected_nic_attributes = copy.deepcopy(DEFAULT_NIC_ATTRIBUTES)
        expected_nic_attributes['sriov']['enabled']['value'] = False
        expected_nic_attributes['sriov']['physnet']['value'] = 'physnet2'
        expected_nic_attributes['dpdk']['enabled']['value'] = False
        self.assertEqual(jsonutils.loads(result['attributes']),
                         expected_nic_attributes)

    def test_upgrade_node_nic_attributes(self):
        interfaces_table = self.meta.tables['node_nic_interfaces']
        result = db.execute(
            sa.select([interfaces_table.c.meta,
                       interfaces_table.c.attributes]).
            where(interfaces_table.c.name == 'test_nic_attributes')
        ).fetchone()

        self.assertEqual(
            jsonutils.loads(result['meta']),
            {
                'offloading_modes': NODE_OFFLOADING_MODES,
                'sriov': {'available': 'test_sriov_available',
                          'pci_id': 'test_sriov_pci_id',
                          'totalvfs': 'test_sriov_totalvfs'},
                'dpdk': {'available': 'test_dpdk_available'},
                'pci_id': 'test_pci_id',
                'numa_node': 12345
            }
        )
        expected_nic_attributes = copy.deepcopy(DEFAULT_NIC_ATTRIBUTES)
        expected_nic_attributes['mtu']['value']['value'] = \
            NODE_NIC_PROPERTIES['mtu']
        expected_nic_attributes['sriov']['enabled']['value'] = \
            NODE_NIC_PROPERTIES['sriov']['enabled']
        expected_nic_attributes['sriov']['numvfs']['value'] = \
            NODE_NIC_PROPERTIES['sriov']['sriov_numvfs']
        expected_nic_attributes['sriov']['physnet']['value'] = \
            NODE_NIC_PROPERTIES['sriov']['physnet']
        expected_nic_attributes['dpdk']['enabled']['value'] = \
            NODE_NIC_PROPERTIES['dpdk']['enabled']
        expected_nic_attributes['offloading']['disable']['value'] = \
            NODE_NIC_PROPERTIES['disable_offloading']
        expected_nic_attributes['offloading']['modes']['value'] = {
            'tx-checksumming': False, 'tx-checksum-sctp': True,
            'tx-checksum-ipv6': False, 'rx-checksumming': None,
            'rx-vlan-offload': None
        }
        self.assertEqual(jsonutils.loads(result['attributes']),
                         expected_nic_attributes)
        # TODO(apopovych): uncomment after removing redundant data
        # self.assertNotIn('offloading_modes', interfaces_table.c)
        # self.assertNotIn('interface_properties', interfaces_table.c)

    def test_upgrade_node_nic_attributes_only_for_cluster_node(self):
        interfaces_table = self.meta.tables['node_nic_interfaces']
        nodes_table = self.meta.tables['nodes']

        result = db.execute(
            sa.select([nodes_table.c.cluster_id, interfaces_table.c.attributes,
                       interfaces_table.c.meta])
            .select_from(interfaces_table.join(
                nodes_table, interfaces_table.c.node_id == nodes_table.c.id))
        )
        for cluster_id, attributes, meta in result:
            self.assertTrue(bool(jsonutils.loads(meta)))
            self.assertEqual(bool(jsonutils.loads(attributes)),
                             bool(cluster_id))

    def test_upgrade_node_bond_attributes_all_defaults(self):
        bonds_table = self.meta.tables['node_bond_interfaces']
        result = db.execute(
            sa.select([bonds_table.c.attributes]).
            where(bonds_table.c.name == 'test_bond_interface')
        ).fetchone()

        expected_attributes = copy.deepcopy(DEFAULT_BOND_ATTRIBUTES)
        expected_attributes['mode']['value']['value'] = 'active-backup'
        self.assertEqual(jsonutils.loads(result['attributes']),
                         expected_attributes)

    def test_upgrade_node_bond_attributes(self):
        bonds_table = self.meta.tables['node_bond_interfaces']
        result = db.execute(
            sa.select([bonds_table.c.attributes]).
            where(bonds_table.c.name == 'test_bond_interface_attributes')
        ).fetchone()

        expected_attributes = copy.deepcopy(DEFAULT_BOND_ATTRIBUTES)
        expected_attributes['mtu']['value']['value'] = 2000
        expected_attributes['lacp_rate']['value']['value'] = 'slow'
        expected_attributes['xmit_hash_policy']['value']['value'] = 'layer2'
        expected_attributes['offloading']['disable']['value'] = False
        expected_attributes['dpdk']['enabled']['value'] = True
        expected_attributes['type__']['value'] = 'linux'
        expected_attributes['mode']['value']['value'] = '802.3ad'
        expected_attributes['offloading']['modes']['value'] = {
            'tx-checksumming': False, 'tx-checksum-sctp': True,
            'rx-checksumming': None, 'rx-vlan-offload': False}
        self.assertEqual(jsonutils.loads(result['attributes']),
                         expected_attributes)
        # TODO(apopovych): uncomment after removing redundant data
        # self.assertNotIn('offloading_modes', bonds_table.c)
        # self.assertNotIn('interface_properties', bonds_table.c)
        # self.assertNotIn('bond_properties', bonds_table.c)


class TestTransactionsNames(base.BaseAlembicMigrationTest):

    def test_field_reset_environment_exist(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [
                {
                    'uuid': 'fake_task_uuid_0',
                    'name': 'reset_environment',
                    'status': 'pending'
                }
            ]
        )

    def test_field_reset_nodes_exist(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [
                {
                    'uuid': 'fake_task_uuid_0',
                    'name': 'reset_nodes',
                    'status': 'pending'
                }
            ]
        )

    def test_field_remove_keys_exist(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [
                {
                    'uuid': 'fake_task_uuid_0',
                    'name': 'remove_keys',
                    'status': 'pending'
                }
            ]
        )

    def test_field_remove_ironic_bootstrap_exist(self):
        db.execute(
            self.meta.tables['tasks'].insert(),
            [
                {
                    'uuid': 'fake_task_uuid_0',
                    'name': 'remove_ironic_bootstrap',
                    'status': 'pending'
                }
            ]
        )
