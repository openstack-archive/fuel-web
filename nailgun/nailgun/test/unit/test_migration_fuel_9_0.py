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

from nailgun.db import db
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base

_prepare_revision = '43b2cb64dae6'
_test_revision = '11a9adc6d36a'


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
            'version': '2015.1-8.0',
            'operating_system': 'ubuntu',
            'state': 'available',
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
            'network_roles_metadata': jsonutils.dumps([{
                'id': 'admin/vip',
                'default_mapping': 'fuelweb_admin',
                'properties': {
                    'subnet': True,
                    'gateway': False,
                    'vip': [
                        {
                            'name': 'release-vip1',
                        },
                        {
                            'name': 'release-vip2',
                            'namespace': 'release-vip2-namespace'
                        }
                    ]
                }
            }]),
            'is_deployable': True,
        }])
    releaseid = result.inserted_primary_key[0]

    db.execute(
        meta.tables['clusters'].insert(),
        [{
            'name': 'test_env',
            'release_id': releaseid,
            'mode': 'ha_compact',
            'status': 'new',
            'net_provider': 'neutron',
            'grouping': 'roles',
            'fuel_version': '8.0',
        }])

    db.execute(
        meta.tables['ip_addrs'].insert(),
        [
            {
                'ip_addr': '192.168.0.2',
                'vip_type': 'management'
            },
            {
                'ip_addr': '192.168.1.2',
                'vip_type': 'haproxy'
            },
            {
                'ip_addr': '192.168.11.2',
                'vip_type': 'my-vip1',
                'namespace': 'my-namespace1'
            },
            {
                'ip_addr': '192.168.12.2',
                'vip_type': 'my-vip2',
                'namespace': 'my-namespace2'
            },
            {
                'ip_addr': '192.168.13.2',
                'vip_type': 'my-vip3',
                'namespace': 'my-namespace3'
            },
            {
                'ip_addr': '192.168.14.2',
                'vip_type': 'my-vip4',
                'namespace': 'my-namespace4'
            },
            {
                'ip_addr': '192.168.15.2',
                'vip_type': 'release-vip2'
            }
        ])

    db.execute(
        meta.tables['network_groups'].insert(),
        [{
            'name': 'public',
            'release': releaseid,
            'meta': jsonutils.dumps({'assign_vip': True})
        }])

    db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_a',
            'title': 'Test plugin A',
            'version': '2.0.0',
            'description': 'Test plugin A for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '4.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['8.0']),
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

    db.execute(
        meta.tables['plugins'].insert(),
        [{
            'name': 'test_plugin_b',
            'title': 'Test plugin B',
            'version': '2.0.0',
            'description': 'Test plugin B for Fuel',
            'homepage': 'http://fuel_plugins.test_plugin.com',
            'package_version': '4.0.0',
            'groups': jsonutils.dumps(['tgroup']),
            'authors': jsonutils.dumps(['tauthor']),
            'licenses': jsonutils.dumps(['tlicense']),
            'releases': jsonutils.dumps([
                {'repository_path': 'repositories/ubuntu'}
            ]),
            'fuel_version': jsonutils.dumps(['8.0']),
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

    db.commit()


class TestNodeGroupsMigration(base.BaseAlembicMigrationTest):

    def test_add_foreign_key_ondelete(self):
        expected_ondelete = {
            'attributes': {
                'attributes_cluster_id_fkey': 'CASCADE'
            },
            'cluster_changes': {
                'cluster_changes_id_fkey': 'CASCADE'
            },
            'nodegroups': {
                'nodegroups_cluster_id_fkey': 'CASCADE'
            },
            'vmware_attributes': {
                'vmware_attributes_cluster_id_fkey': 'CASCADE'
            },
            'networking_configs': {
                'networking_configs_cluster_id_fkey': 'CASCADE'
            },
            'network_groups': {
                'network_groups_nodegroups_fk': 'CASCADE',
                'network_groups_release_fk': 'CASCADE'
            },
            'neutron_config': {
                'neutron_config_id_fkey': 'CASCADE',
            },
            'nodes': {
                'nodes_nodegroups_fk': 'SET NULL',
                'nodes_cluster_id_fkey': 'CASCADE',
            },
            'cluster_plugin_links': {
                'cluster_plugin_links_cluster_id_fkey': 'CASCADE'
            },
            'node_nic_interfaces': {
                'node_nic_interfaces_parent_id_fkey': 'SET NULL'
            },
            'openstack_configs': {
                'openstack_configs_cluster_id_fkey': 'CASCADE',
                'openstack_configs_node_id_fkey': 'SET NULL'
            },
            'plugin_links': {
                'plugin_links_plugin_id_fkey': 'CASCADE'
            },
            'tasks': {
                'tasks_cluster_id_fkey': 'CASCADE',
                'tasks_parent_id_fkey': 'CASCADE'
            },

        }

        for table, fkeys in expected_ondelete.items():
            constraints = self.meta.tables[table].constraints

            for constraint in constraints:
                if constraint.name in fkeys:
                    value = fkeys[constraint.name]
                    self.assertEqual(constraint.ondelete, value)


class TestVipMigration(base.BaseAlembicMigrationTest):
    def test_ip_addrs_vip_name_exists(self):
        result = db.execute(
            sa.select([self.meta.tables['ip_addrs'].c.vip_name]))
        self.assertEqual(result.scalar(), "management")

    def test_ip_addrs_vip_namespace_exists(self):
        result = db.execute(
            sa.select([
                self.meta.tables['ip_addrs'].c.vip_name,
                self.meta.tables['ip_addrs'].c.vip_namespace
            ]))
        result = list(result)
        self.assertItemsEqual(
            (
                ('management', None,),
                ('haproxy', None,),
                ('my-vip1', 'my-namespace1',),
                ('my-vip2', 'my-namespace2',),
                ('my-vip3', 'my-namespace3',),
                ('my-vip4', 'my-namespace4',),
                # namespace has appeared from release network role
                ('release-vip2', 'release-vip2-namespace',),
            ),
            result
        )


class TestNodeRolesMigration(base.BaseAlembicMigrationTest):
    def test_category_is_injected_to_roles_meta(self):
        result = db.execute(
            sa.select([self.meta.tables['releases'].c.roles_metadata])
        )
        rel_row = result.fetchone()

        roles_metadata = jsonutils.loads(rel_row[0])

        role_groups = {
            'controller': 'controller',
            'compute': 'compute',
            'virt': 'compute',
            'compute-vmware': 'compute',
            'ironic': 'compute',
            'cinder': 'storage',
            'cinder-block-device': 'storage',
            'cinder-vmware': 'storage',
            'ceph-osd': 'storage',
            'mongo': 'other',
            'base-os': 'other',
        }

        for role_name in roles_metadata:
            role_group = roles_metadata[role_name].get('group')

            if role_name in role_groups:
                self.assertEquals(role_group, role_groups[role_name])
