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

from nailgun.utils.migration import drop_enum


from alembic import op
from oslo.serialization import jsonutils
import six
import sqlalchemy as sa

from nailgun.db.sqlalchemy.models import fields


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
    extend_plugin_model_upgrade()
    upgrade_node_roles_metadata()
    node_roles_as_plugin_upgrade()


def downgrade():
    node_roles_as_plugin_downgrade()
    extend_plugin_model_downgrade()
    extend_ip_addrs_model_downgrade()

    op.drop_constraint(None, 'oswl_stats', type_='unique')
    op.alter_column(
        'oswl_stats', 'resource_checksum', existing_type=sa.TEXT(),
        nullable=True)
    op.drop_constraint(None, 'nodes', type_='foreignkey')
    op.drop_constraint(None, 'network_groups', type_='foreignkey')


def extend_ip_addrs_model_upgrade():
    op.alter_column('ip_addrs', 'vip_type',
                    type_=sa.String(length=50),
                    existing_type=sa.Enum('haproxy', 'vrouter',
                    name='network_vip_types'))
    drop_enum('network_vip_types')


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


def node_roles_as_plugin_upgrade():
    op.add_column(
        'nodes',
        sa.Column(
            'roles',
            fields.JSON(),
            server_default='[]',
            nullable=False))
    op.add_column(
        'nodes',
        sa.Column(
            'pending_roles',
            fields.JSON(),
            server_default='[]',
            nullable=False))
    op.add_column(
        'nodes',
        sa.Column(
            'primary_roles',
            fields.JSON(),
            server_default='[]',
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
            roles=jsonutils.dumps(rolesmap['roles']),
            pending_roles=jsonutils.dumps(rolesmap['pending_roles']),
            primary_roles=jsonutils.dumps(rolesmap['primary_roles']),
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
