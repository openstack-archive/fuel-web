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

from alembic import op
import six
import sqlalchemy as sa

# revision identifiers, used by Alembic.
from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.db.sqlalchemy.models import fields

revision = '11a9adc6d36a'
down_revision = '43b2cb64dae6'


def upgrade():
    add_foreign_key_ondelete()
    upgrade_ip_address()
    update_vips_from_network_roles()
    upgrade_node_roles_metadata()
    merge_node_attributes_with_nodes()


def downgrade():
    downgrade_merge_node_attributes_with_nodes()
    downgrade_node_roles_metadata()
    remove_foreign_key_ondelete()
    downgrade_ip_address()


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


def upgrade_ip_address():

    op.add_column(
        'ip_addrs',
        sa.Column(
            'is_user_defined',
            sa.Boolean,
            nullable=False,
            default=False,
            server_default="false"
        )
    )

    op.add_column(
        'ip_addrs',
        sa.Column(
            'vip_namespace',
            sa.String(length=25),
            nullable=True,
            default=None,
            server_default=None
        )
    )

    op.alter_column(
        'ip_addrs',
        'vip_type',
        new_column_name='vip_name',
        type_=sa.String(length=25)
    )


def update_vips_from_network_roles():

    def _update_network_roles_from_db_metadata(query):
        connection = op.get_bind()
        _vip_name_to_vip_data = {}

        select = sa.text(query)
        network_roles_metadata = connection.execute(select)
        for network_roles_json in network_roles_metadata:
            if not network_roles_json or not network_roles_json[0]:
                continue
            network_roles = jsonutils.loads(network_roles_json[0])
            # warning: in current schema it is possible that network
            # role is declared as dict
            if isinstance(network_roles, dict):
                network_roles = [network_roles]
            for network_role in network_roles:
                vips = network_role.get('properties', {}).get('vip', [])
                for vip in vips:
                    _vip_name_to_vip_data[vip['name']] = vip
        return _vip_name_to_vip_data

    roles_vip_name_to_vip_data = {}

    # get namespaces from plugins
    roles_vip_name_to_vip_data.update(
        _update_network_roles_from_db_metadata(
            "SELECT network_roles_metadata from plugins"
        )
    )

    # get namespaces from releases
    roles_vip_name_to_vip_data.update(
        _update_network_roles_from_db_metadata(
            "SELECT network_roles_metadata from releases"
        )
    )

    # perform update
    connection = op.get_bind()
    ip_addrs_select = sa.text(
        "SELECT id, vip_name from ip_addrs"
    )
    ip_addrs = connection.execute(ip_addrs_select)

    ip_addrs_update = sa.sql.text(
        "UPDATE ip_addrs "
        "SET vip_namespace = :vip_namespace WHERE id = :id"
    )

    existing_names_to_id = dict(
        (vip_name, vip_id) for (vip_id, vip_name) in ip_addrs
    )

    for vip_name in existing_names_to_id:

        namespace = roles_vip_name_to_vip_data\
            .get(vip_name, {}).get('namespace')

        # update only if namespace arrived
        if namespace:
            connection.execute(
                ip_addrs_update,
                id=existing_names_to_id[vip_name],
                vip_namespace=namespace
            )


def downgrade_ip_address():
    op.alter_column(
        'ip_addrs',
        'vip_name',
        new_column_name='vip_type',
        type_=sa.String(length=25)
    )
    op.drop_column('ip_addrs', 'is_user_defined')
    op.drop_column('ip_addrs', 'vip_namespace')


def upgrade_node_roles_metadata():
    connection = op.get_bind()
    select_query = sa.sql.text("SELECT id, roles_metadata FROM releases")
    update_query = sa.sql.text(
        "UPDATE releases SET roles_metadata = :roles_metadata WHERE id = :id")

    for id, roles_metadata in connection.execute(select_query):
        roles_metadata = jsonutils.loads(roles_metadata)

        role_groups = {
            'controller': 'base',
            'compute': 'compute',
            'virt': 'compute',
            'compute-vmware': 'compute',
            'ironic': 'compute',
            'cinder': 'storage',
            'cinder-block-device': 'storage',
            'cinder-vmware': 'storage',
            'ceph-osd': 'storage'
        }
        for role_name, role_metadata in six.iteritems(roles_metadata):
            role_metadata['group'] = role_groups\
                .get(role_name, consts.NODE_ROLE_GROUPS.other)

        connection.execute(
            update_query,
            id=id,
            roles_metadata=jsonutils.dumps(roles_metadata),
        )


def downgrade_node_roles_metadata():
    connection = op.get_bind()
    select_query = sa.sql.text("SELECT id, roles_metadata FROM releases")
    update_query = sa.sql.text(
        "UPDATE releases SET roles_metadata = :roles_metadata WHERE id = :id")

    for id, roles_metadata in connection.execute(select_query):
        roles_metadata = jsonutils.loads(roles_metadata)
        for role_name, role_metadata in six.iteritems(roles_metadata):
            del role_metadata['group']
        connection.execute(
            update_query,
            id=id,
            roles_metadata=jsonutils.dumps(roles_metadata),
        )


def merge_node_attributes_with_nodes():
    connection = op.get_bind()

    op.add_column(
        'nodes',
        sa.Column(
            'vms_conf',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )

    select_query = sa.sql.text('SELECT node_id, vms_conf FROM node_attributes')
    update_query = sa.sql.text(
        'UPDATE nodes SET vms_conf = :vms_conf WHERE id = :node_id')

    for node_id, vms_conf in connection.execute(select_query):
        connection.execute(update_query, node_id=node_id, vms_conf=vms_conf)

    op.drop_table('node_attributes')


def downgrade_merge_node_attributes_with_nodes():
    op.create_table(
        'node_attributes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=True),
        sa.Column('interfaces', fields.JSON(), nullable=True),
        sa.Column('vms_conf', fields.JSON(),
                  nullable=False, server_default='[]'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.drop_column('nodes', 'vms_conf')
