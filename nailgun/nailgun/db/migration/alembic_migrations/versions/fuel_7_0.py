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

"""Fuel 7.0

Revision ID: 1e50a4903910
Revises: 37608259013
Create Date: 2015-06-24 12:08:04.838393

"""

# revision identifiers, used by Alembic.

revision = '1e50a4903910'
down_revision = '37608259013'

import six
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.sql import text

from alembic import op
from oslo.serialization import jsonutils

from nailgun import consts
from nailgun.db.sqlalchemy.models import fields
from nailgun.extensions.consts import extensions_migration_buffer_table_name
from nailgun import objects
from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import upgrade_enum


task_names_old = (
    'super',
    'deploy',
    'deployment',
    'provision',
    'stop_deployment',
    'reset_environment',
    'update',
    'node_deletion',
    'cluster_deletion',
    'check_before_deployment',
    'check_networks',
    'verify_networks',
    'check_dhcp',
    'verify_network_connectivity',
    'multicast_verification',
    'check_repo_availability',
    'check_repo_availability_with_setup',
    'dump',
    'capacity_log',
    'create_stats_user',
    'remove_stats_user'
)
task_names_new = consts.TASK_NAMES


def upgrade():
    op.create_foreign_key(
        None, 'network_groups', 'nodegroups', ['group_id'], ['id'])
    op.create_foreign_key(
        None, 'nodes', 'nodegroups', ['group_id'], ['id'])
    op.alter_column(
        'oswl_stats', 'resource_checksum', existing_type=sa.TEXT(),
        nullable=False)
    op.create_unique_constraint(
        None, 'oswl_stats', ['cluster_id', 'created_date', 'resource_type'])

    extend_ip_addrs_model_upgrade()
    extend_node_model_upgrade()
    extend_plugin_model_upgrade()
    upgrade_node_roles_metadata()
    node_roles_as_plugin_upgrade()
    migrate_volumes_into_extension_upgrade()
    extend_releases_model_upgrade()
    upgrade_task_names()
    vms_conf_upgrade()
    extend_nic_model_upgrade()
    upgrade_cluster_ui_settings()


def downgrade():
    downgrade_cluster_ui_settings()
    extend_nic_model_downgrade()
    extend_releases_model_downgrade()
    migrate_volumes_into_extension_downgrade()
    node_roles_as_plugin_downgrade()
    extend_plugin_model_downgrade()
    extend_node_model_downgrade()
    extend_ip_addrs_model_downgrade()
    downgrade_task_names()
    vms_conf_downgrade()

    op.drop_constraint(None, 'oswl_stats', type_='unique')
    op.alter_column(
        'oswl_stats', 'resource_checksum', existing_type=sa.TEXT(),
        nullable=True)
    op.drop_constraint(None, 'nodes', type_='foreignkey')
    op.drop_constraint(None, 'network_groups', type_='foreignkey')


def extend_node_model_upgrade():
    op.add_column(
        'node_nic_interfaces',
        sa.Column('offloading_modes',
                  fields.JSON(),
                  nullable=False,
                  server_default='[]'))
    op.add_column(
        'node_bond_interfaces',
        sa.Column('offloading_modes',
                  fields.JSON(),
                  nullable=False,
                  server_default='[]'))

    op.add_column(
        'nodes',
        sa.Column('hostname',
                  sa.Text(),
                  nullable=False,
                  server_default='')
    )
    # upgrade data
    connection = op.get_bind()

    select = text(
        """SELECT id from nodes""")
    update = text(
        """UPDATE nodes
        SET hostname = :hostname
        WHERE id = :id""")
    nodes = connection.execute(select)

    for node in nodes:
        node_id = node[0]
        connection.execute(
            update,
            id=node_id,
            hostname=objects.Node.default_slave_name(node_id)
        )


def extend_node_model_downgrade():
    op.drop_column('node_bond_interfaces', 'offloading_modes')
    op.drop_column('node_nic_interfaces', 'offloading_modes')
    op.drop_column('nodes', 'hostname')


def extend_ip_addrs_model_upgrade():
    op.alter_column('ip_addrs', 'vip_type',
                    type_=sa.String(length=50),
                    existing_type=sa.Enum('haproxy', 'vrouter',
                    name='network_vip_types'))
    drop_enum('network_vip_types')


def upgrade_task_names():
    upgrade_enum(
        "tasks",                    # table
        "name",                     # column
        "task_name",                # ENUM name
        task_names_old,             # old options
        task_names_new              # new options
    )


def downgrade_task_names():
    upgrade_enum(
        "tasks",                    # table
        "name",                     # column
        "task_name",                # ENUM name
        task_names_new,             # old options
        task_names_old              # new options
    )


def vms_conf_upgrade():
    op.add_column(
        'node_attributes',
        sa.Column(
            'vms_conf',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )


def vms_conf_downgrade():
    op.drop_column('node_attributes', 'vms_conf')


def extend_plugin_model_upgrade():
    op.add_column(
        'plugins',
        sa.Column(
            'attributes_metadata',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )
    op.add_column(
        'plugins',
        sa.Column(
            'volumes_metadata',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )
    op.add_column(
        'plugins',
        sa.Column(
            'roles_metadata',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )
    op.add_column(
        'plugins',
        sa.Column(
            'deployment_tasks',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )
    op.add_column(
        'plugins',
        sa.Column(
            'tasks',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )


def extend_ip_addrs_model_downgrade():
    vrouter_enum = sa.Enum('haproxy', 'vrouter',
                           name='network_vip_types')
    vrouter_enum.create(op.get_bind(), checkfirst=False)
    op.alter_column('ip_addrs', 'vip_type', type_=vrouter_enum)


def extend_releases_model_upgrade():
    op.add_column(
        'releases',
        sa.Column(
            'network_roles_metadata',
            fields.JSON(),
            server_default='[]'))


def extend_plugin_model_downgrade():
    op.drop_column('plugins', 'tasks')
    op.drop_column('plugins', 'deployment_tasks')
    op.drop_column('plugins', 'roles_metadata')
    op.drop_column('plugins', 'volumes_metadata')
    op.drop_column('plugins', 'attributes_metadata')


def upgrade_node_roles_metadata():
    connection = op.get_bind()
    select_query = sa.sql.text("SELECT id, roles_metadata FROM releases")
    update_query = sa.sql.text(
        "UPDATE releases SET roles_metadata = :roles_metadata WHERE id = :id")

    for id, roles_metadata in connection.execute(select_query):
        roles_metadata = jsonutils.loads(roles_metadata)
        for role, role_info in six.iteritems(roles_metadata):
            if role in ['controller', 'zabbix-server']:
                role_info['public_ip_required'] = True
        connection.execute(
            update_query,
            id=id,
            roles_metadata=jsonutils.dumps(roles_metadata))


def migrate_volumes_into_extension_upgrade():
    """Migrate data into intermediate table, from
    which specific extensions will be able to retrieve
    the data. It allows us not to hardcode extension
    tables in core migrations.
    """
    connection = op.get_bind()

    # Create migration buffer table for extensions
    op.create_table(
        extensions_migration_buffer_table_name,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('extension_name', sa.Text(), nullable=False),
        sa.Column('data', fields.JSON()),
        sa.PrimaryKeyConstraint('id'))

    select_query = sa.sql.text("SELECT node_id, volumes FROM node_attributes")
    insert_query = sa.sql.text(
        "INSERT INTO {0} (extension_name, data)"
        "VALUES (:extension_name, :data)".format(
            extensions_migration_buffer_table_name))

    # Fill in the buffer
    for node_id, volumes in connection.execute(select_query):
        connection.execute(
            insert_query,
            data=jsonutils.dumps({
                'node_id': node_id,
                'volumes': jsonutils.loads(volumes)}),
            extension_name='volume_manager')

    # Drop the table after the data were migrated
    op.drop_column('node_attributes', 'volumes')


def migrate_volumes_into_extension_downgrade():
    # NOTE(eli): we don't support data downgrade, so we just change
    # schema to represent previous db schema state
    op.drop_table(extensions_migration_buffer_table_name)
    op.add_column(
        'node_attributes',
        sa.Column('volumes', fields.JSON(), nullable=True))


def node_roles_as_plugin_upgrade():
    op.add_column(
        'nodes',
        sa.Column(
            'roles',
            psql.ARRAY(sa.String(64)),
            server_default='{}',
            nullable=False))
    op.add_column(
        'nodes',
        sa.Column(
            'pending_roles',
            psql.ARRAY(sa.String(64)),
            server_default='{}',
            nullable=False))
    op.add_column(
        'nodes',
        sa.Column(
            'primary_roles',
            psql.ARRAY(sa.String(64)),
            server_default='{}',
            nullable=False))

    connection = op.get_bind()

    # map assoc table to new node columns
    assoc_column_map = {
        'node_roles': 'roles',
        'pending_node_roles': 'pending_roles',
    }

    # select all node-role associations for both roles and pending roles,
    # and gather this information in one dictionary
    node_roles_map = {}
    for assoc_table, column in six.iteritems(assoc_column_map):
        result = connection.execute(sa.text("""
            SELECT nodes.id, roles.name, {assoc_table}.primary
            FROM {assoc_table}
                INNER JOIN roles ON {assoc_table}.role = roles.id
                INNER JOIN nodes ON {assoc_table}.node = nodes.id
            """.format(assoc_table=assoc_table)))

        for nodeid, role, primary in result:
            if nodeid not in node_roles_map:
                node_roles_map[nodeid] = {
                    'roles': [], 'pending_roles': [], 'primary_roles': []}

            if primary:
                node_roles_map[nodeid]['primary_roles'].append(role)

            node_roles_map[nodeid][column].append(role)

    # apply gathered node-role information to new columns
    for nodeid, rolesmap in six.iteritems(node_roles_map):
        connection.execute(
            sa.text("""UPDATE nodes
                       SET roles = :roles,
                           pending_roles = :pending_roles,
                           primary_roles = :primary_roles
                       WHERE id = :id"""),
            id=nodeid,
            roles=rolesmap['roles'],
            pending_roles=rolesmap['pending_roles'],
            primary_roles=rolesmap['primary_roles'],
        )

    # remove legacy tables
    op.drop_table('node_roles')
    op.drop_table('pending_node_roles')
    op.drop_table('roles')


def node_roles_as_plugin_downgrade():
    op.create_table(
        'roles',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column(
            'release_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            'name', sa.VARCHAR(length=50), autoincrement=False,
            nullable=False),
        sa.ForeignKeyConstraint(
            ['release_id'], [u'releases.id'], name=u'roles_release_id_fkey',
            ondelete=u'CASCADE'),
        sa.PrimaryKeyConstraint('id', name=u'roles_pkey'),
        sa.UniqueConstraint(
            'name', 'release_id', name=u'roles_name_release_id_key'))

    op.create_table(
        'node_roles',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('role', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('node', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('primary', sa.BOOLEAN(), server_default=sa.text(u'false'),
                  autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ['node'], [u'nodes.id'], name=u'node_roles_node_fkey',
            ondelete=u'CASCADE'),
        sa.ForeignKeyConstraint(
            ['role'], [u'roles.id'],
            name=u'node_roles_role_fkey', ondelete=u'CASCADE'),
        sa.PrimaryKeyConstraint('id', name=u'node_roles_pkey'))

    op.create_table(
        'pending_node_roles',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('role', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('node', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            'primary', sa.BOOLEAN(), server_default=sa.text(u'false'),
            autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ['node'], [u'nodes.id'], name=u'pending_node_roles_node_fkey',
            ondelete=u'CASCADE'),
        sa.ForeignKeyConstraint(
            ['role'], [u'roles.id'], name=u'pending_node_roles_role_fkey',
            ondelete=u'CASCADE'),
        sa.PrimaryKeyConstraint('id', name=u'pending_node_roles_pkey'))

    # NOTE(ikalnitsky):
    #
    # WE DO NOT SUPPORT DOWNGRADE DATE MIGRATION BY HISTORICAL REASONS.
    # SO ANY DOWNGRADE WILL LOST DATA.

    op.drop_column('nodes', 'primary_roles')
    op.drop_column('nodes', 'pending_roles')
    op.drop_column('nodes', 'roles')


def extend_releases_model_downgrade():
    op.drop_column('releases', 'network_roles_metadata')


def extend_nic_model_upgrade():
    connection = op.get_bind()
    op.add_column(
        'node_nic_interfaces',
        sa.Column('pxe',
                  sa.Boolean,
                  nullable=False,
                  server_default='false'))
    select_query = sa.sql.text(
        "SELECT ni.id from node_nic_interfaces ni "
        "join net_nic_assignments na on ni.id=na.interface_id "
        "join network_groups ng on ng.id=na.network_id "
        "WHERE ng.name = 'fuelweb_admin'")
    update_query = sa.sql.text(
        "UPDATE node_nic_interfaces SET pxe = true "
        "WHERE id = :id")

    # change 'pxe' property to 'true' value for admin ifaces
    for iface_id in connection.execute(select_query):
        connection.execute(update_query, id=iface_id[0])


def extend_nic_model_downgrade():
    op.drop_column('node_nic_interfaces', 'pxe')


def upgrade_cluster_ui_settings():
    op.add_column(
        'clusters',
        sa.Column(
            'ui_settings',
            fields.JSON(),
            server_default='{"view_mode": "standard", "grouping": "roles"}',
            nullable=False
        )
    )
    op.drop_column('clusters', 'grouping')


def downgrade_cluster_ui_settings():
    op.add_column(
        'clusters',
        sa.Column(
            'grouping',
            sa.Enum(
                'roles', 'hardware', 'both', name='cluster_grouping'),
            nullable=False,
            default=consts.CLUSTER_GROUPING.roles
        )
    )
    op.drop_column('clusters', 'ui_settings')
