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

_prepare_revision = '43b2cb64dae6'
_test_revision = '11a9adc6d36a'


import alembic
from nailgun.db import dropdb
from nailgun.db.migration import ALEMBIC_CONFIG
from nailgun.test import base


def setup_module():
    dropdb()
    alembic.command.upgrade(ALEMBIC_CONFIG, _prepare_revision)
    prepare()
    alembic.command.upgrade(ALEMBIC_CONFIG, _test_revision)


def prepare():
    pass


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
