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
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '675105097a69'
_test_revision = 'c6edea552f1e'

JSON_TASKS = [
    {
        'id': 'post_deployment_end',
        'type': 'stage',
        'requires': ['post_deployment_start']
    },
    {
        'id': 'primary-controller',
        'parameters': {'strategy': {'type': 'one_by_one'}},
        'required_for': ['deploy_end'],
        'requires': ['deploy_start'],
        'role': ['primary-controller'],  # legacy notation should be converted
                                         # to `roles`
        'type': 'group'
    },
    {
        'id': 'cross-dep-test',
        'type': 'puppet',
        'cross-depended-by': ['a', 'b'],
        'cross-depends': ['c', 'd']
    },
    {
        'id': 'custom-test',
        'type': 'puppet',
        'test_pre': {'k': 'v'},
        'test_post': {'k': 'v'}
    }
]

DEPLOYMENT_INFO = {
    55: {
        'master': {
            'attr1': 1,
            'attr2': 2
        },
        '1': {
            'attr1': 3,
            'attr2': 4
        },
        '2': {
            'attr1': 5,
            'attr2': 6
        }
    },
    56: {
        'master': {
            'attr1': 7,
            'attr2': 8
        },
        '1': {
            'attr1': 9,
            'attr2': 10
        },
        '2': {
            'attr1': 11,
            'attr2': 12
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
            'deployment_tasks': jsonutils.dumps(JSON_TASKS),
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
            'is_deployable': True
        }])

    release_id = result.inserted_primary_key[0]

    cluster_ids = []
    for cluster_name in ['test_env1', 'test_env2']:
        result = db.execute(
            meta.tables['clusters'].insert(),
            [{
                'name': cluster_name,
                'release_id': release_id,
                'mode': 'ha_compact',
                'status': 'new',
                'net_provider': 'neutron',
                'grouping': 'roles',
                'fuel_version': '10.0',
                'deployment_tasks': jsonutils.dumps(JSON_TASKS)
            }])
        cluster_ids.append(result.inserted_primary_key[0])

    result = db.execute(
        meta.tables['nodes'].insert(),
        [{
            'uuid': '26b508d0-0d76-4159-bce9-f67ec2765480',
            'cluster_id': None,
            'group_id': None,
            'status': 'discover',
            'meta': jsonutils.dumps({
                "interfaces": [{
                    "mac": '00:00:00:00:00:01'
                }]
            }),
            'mac': 'aa:aa:aa:aa:aa:aa',
            'timestamp': datetime.datetime.utcnow(),
        }]
    )
    node_id = result.inserted_primary_key[0]

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
            'deployment_tasks': jsonutils.dumps(JSON_TASKS),
            'fuel_version': jsonutils.dumps(['10.0']),
            'network_roles_metadata': jsonutils.dumps([{
                'id': 'admin/vip',
                'default_mapping': 'fuelweb_admin',
                'properties': {
                    'subnet': True,
                    'gateway': False,
                    'vip': [
                        {
                            'name': 'my-vip1',
                            'namespace': 'my-namespace1',
                        },
                        {
                            'name': 'my-vip2',
                            'namespace': 'my-namespace2',
                        }
                    ]
                }
            }])
        }]
    )
    plugin_a_id = result.inserted_primary_key[0]

    result = db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_b',
            'title': 'Test plugin B',
            'version': '2.0.0',
            'description': 'Test plugin B for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '5.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['10.0']),
            'network_roles_metadata': jsonutils.dumps([{
                'id': 'admin/vip',
                'default_mapping': 'fuelweb_admin',
                'properties': {
                    'subnet': True,
                    'gateway': False,
                    'vip': [
                        {
                            'name': 'my-vip3',
                            'namespace': 'my-namespace3',
                        },
                        {
                            'name': 'my-vip4',
                            'namespace': 'my-namespace4',
                        }
                    ]
                }
            }])
        }]
    )
    plugin_b_id = result.inserted_primary_key[0]

    db.execute(
        meta.tables['cluster_plugin_links'].insert(),
        [
            {
                'cluster_id': cluster_ids[0],
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description',
                'hidden': False
            },
            # this is duplicate, should be deleted during migration
            {
                'cluster_id': cluster_ids[1],
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description_duplicate',
                'hidden': False
            },
            # duplicate by URL but in another cluster, should
            # not be deleted
            {
                'cluster_id': cluster_ids[0],
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description',
                'hidden': False
            }
        ]
    )

    db.execute(
        meta.tables['cluster_plugins'].insert(),
        [
            {'cluster_id': cluster_ids[0], 'plugin_id': plugin_a_id},
            {'cluster_id': cluster_ids[0], 'plugin_id': plugin_b_id}
        ]
    )

    db.execute(
        meta.tables['plugin_links'].insert(),
        [
            {
                'plugin_id': plugin_a_id,
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description',
                'hidden': False
            },
            # this is duplicate, should be deleted during migration
            {
                'plugin_id': plugin_b_id,
                'title': 'title',
                'url': 'http://www.zzz.com',
                'description': 'description_duplicate',
                'hidden': False
            }
        ]
    )

    db.execute(
        meta.tables['node_nic_interfaces'].insert(),
        [{
            'node_id': node_id,
            'name': 'test_interface',
            'mac': '00:00:00:00:00:01',
            'max_speed': 200,
            'current_speed': 100,
            'ip_addr': '10.20.0.2',
            'netmask': '255.255.255.0',
            'state': 'test_state',
            'interface_properties': jsonutils.dumps(
                {'test_property': 'test_value'}),
            'driver': 'test_driver',
            'bus_info': 'some_test_info'
        }]
    )

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

    result = db.execute(
        meta.tables['tasks'].insert(),
        [
            {
                'id': 55,
                'uuid': '219eaafe-01a1-4f26-8edc-b9d9b0df06b3',
                'name': 'deployment',
                'status': 'running',
                'deployment_info': jsonutils.dumps(DEPLOYMENT_INFO[55])
            },
            {
                'id': 56,
                'uuid': 'a45fbbcd-792c-4245-a619-f4fb2f094d38',
                'name': 'deployment',
                'status': 'running',
                'deployment_info': jsonutils.dumps(DEPLOYMENT_INFO[56])
            }
        ]
    )
    TestRequiredComponentTypesField.prepare(meta)
    TestNodeNICAttributesMigration.prepare(meta, cluster_ids[0])
    db.commit()


class TestPluginLinksConstraints(base.BaseAlembicMigrationTest):
    # see initial data in setup section
    def test_plugin_links_duplicate_cleanup(self):
        links_count = db.execute(
            sa.select(
                [sa.func.count(self.meta.tables['plugin_links'].c.id)]
            )).fetchone()[0]
        self.assertEqual(links_count, 1)

    def test_cluster_plugin_links_duplicate_cleanup(self):
        links_count = db.execute(
            sa.select(
                [sa.func.count(self.meta.tables['cluster_plugin_links'].c.id)]
            )).fetchone()[0]
        self.assertEqual(links_count, 2)


class TestNodeNICAttributesMigration(base.BaseAlembicMigrationTest):
    default_nic_attributes = {
        "offloading": {
            "disable": {"type": "checkbox", "value": False,
                        "weight": 10, "label": "Disable offloading"},
            "modes": {"value": {}, "type": "offloading_modes",
                      "description": "Offloading modes", "weight": 20,
                      "label": "Offloading modes"},
            "metadata": {"weight": 10, "label": "Offloading"}
        },
        "mtu": {
            "value": {"type": "text", "value": None, "weight": 10,
                      "label": "MTU"},
            "metadata": {"weight": 20, "label": "MTU"}
        },
        "sriov": {
            "numvfs": {"min": 0, "type": "number", "value": None,
                       "weight": 20, "label": "Virtual functions"},
            "enabled": {"type": "checkbox", "value": None,
                        "weight": 10, "label": "SRIOV enabled"},
            "physnet": {"type": "text", "value": "", "weight": 30,
                        "label": "Physical network"},
            "metadata": {"weight": 30, "label": "SRIOV"}
        },
        "dpdk": {
            "enabled": {"type": "checkbox", "value": None,
                        "weight": 10, "label": "DPDK enabled"},
            "metadata": {"weight": 40, "label": "DPDK"}
        }
    }
    default_bond_attributes = {}
    nic_attributes_data = {
        "mtu": "test_mtu",
        "disable_offloading": "test_disable_offloading",
        "sriov": {
            "available": "test_sriov_available",
            "sriov_numvfs": "test_sriov_sriov_numvfs",
            "enabled": "test_sriov_enabled",
            "pci_id": "test_sriov_pci_id",
            "sriov_totalvfs": "test_sriov_totalvfs",
            "physnet": "test_sriov_physnet"
        },
        "dpdk":  {
            "available": "test_dpdk_available",
            "enabled": "test_dpdk_enabled",
        },
        'pci_id': "test_pci_id",
        'numa_node': 12345
    }

    @classmethod
    def prepare(cls, meta, cluster_id):
        result = db.execute(
            meta.tables['nodes'].insert(),
            [{
                 'uuid': '26b508d0-0d76-4159-bce9-f67ec2765481',
                 'cluster_id': cluster_id,
                 'group_id': None,
                 'status': 'discover',
                 'meta': jsonutils.dumps({
                     "interfaces": [
                         {
                             "name": "test_nic_empty_attributes",
                             "mac": "00:00:00:00:00:01",
                             "interface_properties": {}
                         },
                         {
                             "name": "test_nic_attributes",
                             "mac": "00:00:00:00:00:02",
                             "interface_properties": cls.nic_attributes_data
                         }
                     ]
                 }),
                 'mac': 'aa:aa:aa:aa:aa:ab',
                 'timestamp': datetime.datetime.utcnow(),
            }]
        )
        node_id = result.inserted_primary_key[0]

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

        db.execute(
            meta.tables['node_nic_interfaces'].insert(),
            [{
                'node_id': node_id,
                'name': 'test_nic_attributes',
                'mac': '00:00:00:00:00:02',
                'interface_properties': jsonutils.dumps(
                    cls.nic_attributes_data),
                'offloading_modes': jsonutils.dumps([
                    {
                        "state": True,
                        "name": "tx-checksumming",
                        "sub": [{
                            "state": True,
                            "name": "tx-checksum-sctp",
                            "sub": []
                        }, {
                            "state": False,
                            "name": "tx-checksum-ipv6",
                            "sub": []
                        }]
                    },
                    {
                        "state": None,
                        "name": "rx-checksumming",
                        "sub": []
                    }
                ])
            }]
        )

    def test_upgrade_release_with_nic_attributes(self):
        releases_table = self.meta.tables['releases']
        result = db.execute(
            sa.select([releases_table.c.nic_attributes,
                       releases_table.c.bond_attributes])
        ).fetchone()
        self.assertEqual(self.default_nic_attributes,
                         jsonutils.loads(result['nic_attributes']))
        self.assertEqual(self.default_bond_attributes,
                         jsonutils.loads(result['bond_attributes']))

    def test_upgrade_node_nic_attributes_with_empty_properties(self):
        interfaces_table = self.meta.tables['node_nic_interfaces']
        result = db.execute(
            sa.select([interfaces_table.c.meta,
                       interfaces_table.c.attributes]).
            where(interfaces_table.c.name == "test_nic_empty_attributes")
        ).fetchone()

        self.assertEqual(
            jsonutils.loads(result['meta']),
            {'offloading_modes': [], 'sriov': {'available': False,
                                               'pci_id': '', 'totalvfs': 0},
             'dpdk': {'available': False}, 'pci_id': '', 'numa_node': None}
        )
        expected_nic_attributes = copy.deepcopy(self.default_nic_attributes)
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
            where(interfaces_table.c.name == "test_nic_attributes")
        ).fetchone()

        self.assertEqual(jsonutils.loads(result['meta']),
                         {'offloading_modes': [],
                          'sriov': {'available': 'test_sriov_available',
                                    'pci_id': 'test_sriov_pci_id',
                                    'totalvfs': 'test_sriov_totalvfs'},
                          'dpdk': {'available': 'test_dpdk_available'},
                          'pci_id': 'test_pci_id',
                          'numa_node': 12345})
        expected_nic_attributes = copy.deepcopy(self.default_nic_attributes)
        expected_nic_attributes['mtu']['value']['value'] = \
            self.nic_attributes_data['mtu']
        expected_nic_attributes['sriov']['enabled']['value'] = \
            self.nic_attributes_data['sriov']['enabled']
        expected_nic_attributes['sriov']['numvfs']['value'] = \
            self.nic_attributes_data['sriov']['sriov_numvfs']
        expected_nic_attributes['sriov']['physnet']['value'] = \
            self.nic_attributes_data['sriov']['physnet']
        expected_nic_attributes['dpdk']['enabled']['value'] = \
            self.nic_attributes_data['dpdk']['enabled']
        expected_nic_attributes['offloading']['disable']['value'] = \
            self.nic_attributes_data['disable_offloading']
        expected_nic_attributes['offloading']['modes']['value'] = {
            'tx-checksumming': True, 'tx-checksum-sctp': True,
            'tx-checksum-ipv6': False, 'rx-checksumming': None
        }
        self.assertEqual(jsonutils.loads(result['attributes']),
                         expected_nic_attributes)

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


class TestPluginAttributesMigration(base.BaseAlembicMigrationTest):
    def test_new_attributes_fields_exist(self):
        node_bond_interfaces_table = self.meta.tables['node_bond_interfaces']
        plugins_table = self.meta.tables['plugins']
        columns = [
            plugins_table.c.nic_attributes_metadata,
            plugins_table.c.bond_attributes_metadata,
            plugins_table.c.node_attributes_metadata,
            node_bond_interfaces_table.c.attributes,
        ]

        for column in columns:
            db_values = db.execute(sa.select([column])).fetchone()
            for db_value in db_values:
                self.assertEqual(db_value, '{}')

    def test_node_nic_interface_cluster_plugins_creation(self):
        node_nic_interface_cluster_plugins = \
            self.meta.tables['node_nic_interface_cluster_plugins']
        cluster_plugins = self.meta.tables['cluster_plugins']
        node_nic_interfaces = self.meta.tables['node_nic_interfaces']
        nodes = self.meta.tables['nodes']

        cluster_plugin_id = db.execute(sa.select([cluster_plugins])).scalar()
        interface_id = db.execute(sa.select([node_nic_interfaces])).scalar()
        node_id = db.execute(sa.select([nodes])).scalar()

        db.execute(
            node_nic_interface_cluster_plugins.insert(),
            [{
                'cluster_plugin_id': cluster_plugin_id,
                'interface_id': interface_id,
                'node_id': node_id,
                'attributes': jsonutils.dumps({'test_attr': 'test'})
            }])

    def test_node_bond_interface_cluster_plugins_creation(self):
        node_bond_interface_cluster_plugins = \
            self.meta.tables['node_bond_interface_cluster_plugins']
        cluster_plugins = self.meta.tables['cluster_plugins']
        node_bond_interfaces = self.meta.tables['node_bond_interfaces']
        nodes = self.meta.tables['nodes']

        cluster_plugin_id = db.execute(sa.select([cluster_plugins])).scalar()
        bond_id = db.execute(sa.select([node_bond_interfaces])).scalar()
        node_id = db.execute(sa.select([nodes])).scalar()

        db.execute(
            node_bond_interface_cluster_plugins.insert(),
            [{
                'cluster_plugin_id': cluster_plugin_id,
                'bond_id': bond_id,
                'node_id': node_id,
                'attributes': jsonutils.dumps({'test_attr': 'test'})
            }])

    def test_node_cluster_plugins_creation(self):
        node_cluster_plugins = self.meta.tables['node_cluster_plugins']
        cluster_plugins = self.meta.tables['cluster_plugins']
        nodes = self.meta.tables['nodes']

        cluster_plugin_id = db.execute(sa.select([cluster_plugins])).scalar()
        node_id = db.execute(sa.select([nodes])).scalar()

        db.execute(
            node_cluster_plugins.insert(),
            [{
                'cluster_plugin_id': cluster_plugin_id,
                'node_id': node_id,
                'attributes': jsonutils.dumps({'test_attr': 'test'})
            }])


class TestSplitDeploymentInfo(base.BaseAlembicMigrationTest):

    def test_split_deployment_info(self):
        node_di_table = self.meta.tables['node_deployment_info']
        res = db.execute(sa.select([node_di_table]))
        for data in res:
            self.assertEqual(jsonutils.loads(data.deployment_info),
                             DEPLOYMENT_INFO[data.task_id][data.node_uid])

        tasks_table = self.meta.tables['tasks']
        res = db.execute(sa.select([tasks_table]))
        for data in res:
            self.assertIsNone(data.deployment_info)


class TestRequiredComponentTypesField(base.BaseAlembicMigrationTest):
    release_name = 'test_release'
    version = '2015.1-10.0'

    @classmethod
    def prepare(cls, meta):
        db.execute(
            meta.tables['releases'].insert(),
            [{
                'name': cls.release_name,
                'version': cls.version,
                'operating_system': 'ubuntu',
                'state': 'available',
                'roles_metadata': '{}',
                'is_deployable': True
            }])

    def test_upgrade_release_required_component_types(self):
        releases_table = self.meta.tables['releases']
        result = db.execute(
            sa.select([releases_table.c.required_component_types]).
            where(releases_table.c.name == self.release_name).
            where(releases_table.c.version == self.version)).fetchone()
        self.assertEqual(jsonutils.loads(result['required_component_types']),
                         ['hypervisor', 'network', 'storage'])

    def test_not_nullable_required_component_types(self):
        with self.assertRaisesRegexp(
                IntegrityError,
                'null value in column "required_component_types" '
                'violates not-null constraint'
        ):
            db.execute(
                self.meta.tables['releases'].insert(),
                {
                    'name': 'test_release',
                    'version': '2015.1-10.0',
                    'operating_system': 'ubuntu',
                    'state': 'available',
                    'roles_metadata': '{}',
                    'is_deployable': True,
                    'required_component_types': None
                })
        db.rollback()
