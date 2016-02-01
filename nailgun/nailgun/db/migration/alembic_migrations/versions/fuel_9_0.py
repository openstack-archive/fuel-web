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

"""Fuel 9.0

Revision ID: 11a9adc6d36a
Revises: 2f879fa32f00
Create Date: 2015-12-15 17:20:49.519542

"""

# revision identifiers, used by Alembic.
revision = '11a9adc6d36a'
down_revision = '43b2cb64dae6'

from alembic import op  # noqa
import sqlalchemy as sa  # noqa


def upgrade():
    add_foreign_key_ondelete()


def downgrade():
    remove_foreign_key_ondelete()


def remove_foreign_key_ondelete():
    op.drop_constraint(
        'attributes_cluster_id_fkey',
        'attributes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'attributes_cluster_id_fkey',
        'attributes', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'cluster_changes_cluster_id_fkey',
        'cluster_changes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'cluster_changes_cluster_id_fkey',
        'cluster_changes', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'nodegroups_cluster_id_fkey',
        'nodegroups',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodegroups_cluster_id_fkey',
        'nodegroups', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'networking_configs_cluster_id_fkey',
        'networking_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'networking_configs_cluster_id_fkey',
        'networking_configs', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'network_groups_nodegroups_fk',
        'network_groups',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'network_groups_nodegroups_fk',
        'network_groups', 'nodegroups',
        ['group_id'], ['id'],
    )

    op.drop_constraint(
        'neutron_config_id_fkey',
        'neutron_config',
        type_='foreignkey'
    )

    op.create_foreign_key(
        'neutron_config_id_fkey',
        'neutron_config', 'networking_configs',
        ['id'], ['id'],
    )

    op.drop_constraint(
        'nodes_nodegroups_fk',
        'nodes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodes_nodegroups_fk',
        'nodes', 'nodegroups',
        ['group_id'], ['id'],
    )

    op.drop_constraint(
        'nodes_cluster_id_fkey',
        'nodes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodes_cluster_id_fkey',
        'nodes', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'cluster_plugin_links_cluster_id_fkey',
        'cluster_plugin_links',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'cluster_plugin_links_cluster_id_fkey',
        'cluster_plugin_links', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'node_nic_interfaces_parent_id_fkey',
        'node_nic_interfaces',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'node_nic_interfaces_parent_id_fkey',
        'node_nic_interfaces', 'node_bond_interfaces',
        ['parent_id'], ['id'],
    )

    op.drop_constraint(
        'openstack_configs_cluster_id_fkey',
        'openstack_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'openstack_configs_cluster_id_fkey',
        'openstack_configs', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'openstack_configs_node_id_fkey',
        'openstack_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'openstack_configs_node_id_fkey',
        'openstack_configs', 'nodes',
        ['node_id'], ['id'],
    )

    op.drop_constraint(
        'plugin_links_plugin_id_fkey',
        'plugin_links',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'plugin_links_plugin_id_fkey',
        'plugin_links', 'plugins',
        ['plugin_id'], ['id'],
    )

    op.drop_constraint(
        'tasks_cluster_id_fkey',
        'tasks',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'tasks_cluster_id_fkey',
        'tasks', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'tasks_parent_id_fkey',
        'tasks',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'tasks_parent_id_fkey',
        'tasks', 'tasks',
        ['parent_id'], ['id'],
    )


def add_foreign_key_ondelete():
    op.drop_constraint(
        'attributes_cluster_id_fkey',
        'attributes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'attributes_cluster_id_fkey',
        'attributes', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'cluster_changes_cluster_id_fkey',
        'cluster_changes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'cluster_changes_cluster_id_fkey',
        'cluster_changes', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'nodegroups_cluster_id_fkey',
        'nodegroups',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodegroups_cluster_id_fkey',
        'nodegroups', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'networking_configs_cluster_id_fkey',
        'networking_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'networking_configs_cluster_id_fkey',
        'networking_configs', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'network_groups_nodegroups_fk',
        'network_groups',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'network_groups_nodegroups_fk',
        'network_groups', 'nodegroups',
        ['group_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'network_groups_release_fkey',
        'network_groups',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'network_groups_release_fk',
        'network_groups', 'releases',
        ['release'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'neutron_config_id_fkey',
        'neutron_config',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'neutron_config_id_fkey',
        'neutron_config', 'networking_configs',
        ['id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'nodes_nodegroups_fk',
        'nodes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodes_nodegroups_fk',
        'nodes', 'nodegroups',
        ['group_id'], ['id'],
        ondelete='SET NULL'
    )

    op.drop_constraint(
        'nodes_cluster_id_fkey',
        'nodes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodes_cluster_id_fkey',
        'nodes', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'cluster_plugin_links_cluster_id_fkey',
        'cluster_plugin_links',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'cluster_plugin_links_cluster_id_fkey',
        'cluster_plugin_links', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'node_nic_interfaces_parent_id_fkey',
        'node_nic_interfaces',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'node_nic_interfaces_parent_id_fkey',
        'node_nic_interfaces', 'node_bond_interfaces',
        ['parent_id'], ['id'],
        ondelete='SET NULL'
    )

    op.drop_constraint(
        'openstack_configs_cluster_id_fkey',
        'openstack_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'openstack_configs_cluster_id_fkey',
        'openstack_configs', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'openstack_configs_node_id_fkey',
        'openstack_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'openstack_configs_node_id_fkey',
        'openstack_configs', 'nodes',
        ['node_id'], ['id'],
        ondelete='SET NULL'
    )

    op.drop_constraint(
        'plugin_links_plugin_id_fkey',
        'plugin_links',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'plugin_links_plugin_id_fkey',
        'plugin_links', 'plugins',
        ['plugin_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'tasks_cluster_id_fkey',
        'tasks',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'tasks_cluster_id_fkey',
        'tasks', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'tasks_parent_id_fkey',
        'tasks',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'tasks_parent_id_fkey',
        'tasks', 'tasks',
        ['parent_id'], ['id'],
        ondelete='CASCADE'
    )
