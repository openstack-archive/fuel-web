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

from alembic import op
import sqlalchemy as sa

from nailgun.db.sqlalchemy.models import fields


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_foreign_key(
        None, 'network_groups', 'nodegroups', ['group_id'], ['id'])
    op.create_foreign_key(
        None, 'nodes', 'nodegroups', ['group_id'], ['id'])
    op.alter_column(
        'oswl_stats', 'resource_checksum', existing_type=sa.TEXT(),
        nullable=False)
    op.create_unique_constraint(
        None, 'oswl_stats', ['cluster_id', 'created_date', 'resource_type'])
    ### end Alembic commands ###

    node_roles_as_plugin_upgrade()


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'oswl_stats', type_='unique')
    op.alter_column(
        'oswl_stats', 'resource_checksum', existing_type=sa.TEXT(),
        nullable=True)
    op.drop_constraint(None, 'nodes', type_='foreignkey')
    op.drop_constraint(None, 'network_groups', type_='foreignkey')
    ### end Alembic commands ###

    node_roles_as_plugin_downgrade()


def node_roles_as_plugin_upgrade():
    op.add_column(
        'nodes', sa.Column('roles', fields.JSON(), nullable=True))
    op.add_column(
        'nodes', sa.Column('pending_roles', fields.JSON(), nullable=True))
    op.add_column(
        'nodes', sa.Column('primary_roles', fields.JSON(), nullable=True))

    # TODO: migrate all existing roles tables

    op.alter_column(
        'nodes', 'roles', existing_type=fields.JSON(), nullable=False)
    op.alter_column(
        'nodes', 'pending_roles', existing_type=fields.JSON(), nullable=False)
    op.alter_column(
        'nodes', 'primary_roles', existing_type=fields.JSON(), nullable=False)

    # remove legacy tables
    # op.drop_table('roles')
    # op.drop_table('pending_node_roles')
    # op.drop_table('node_roles')


def node_roles_as_plugin_downgrade():
    op.create_table('node_roles',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('role', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('node', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('primary', sa.BOOLEAN(), server_default=sa.text(u'false'),
                  autoincrement=False, nullable=False),

        sa.ForeignKeyConstraint(
            ['node'], [u'nodes.id'], name=u'node_roles_node_fkey',
            ondelete=u'CASCADE'),
        sa.ForeignKeyConstraint(['role'], [u'roles.id'], name=u'node_roles_role_fkey', ondelete=u'CASCADE'),
        sa.PrimaryKeyConstraint('id', name=u'node_roles_pkey')
    )
    op.create_table('pending_node_roles',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('role', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('node', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('primary', sa.BOOLEAN(), server_default=sa.text(u'false'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['node'], [u'nodes.id'], name=u'pending_node_roles_node_fkey', ondelete=u'CASCADE'),
    sa.ForeignKeyConstraint(['role'], [u'roles.id'], name=u'pending_node_roles_role_fkey', ondelete=u'CASCADE'),
    sa.PrimaryKeyConstraint('id', name=u'pending_node_roles_pkey')
    )
    op.create_table('roles',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('release_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('name', sa.VARCHAR(length=50), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['release_id'], [u'releases.id'], name=u'roles_release_id_fkey', ondelete=u'CASCADE'),
    sa.PrimaryKeyConstraint('id', name=u'roles_pkey'),
    sa.UniqueConstraint('name', 'release_id', name=u'roles_name_release_id_key')
    )

    op.drop_column('nodes', 'primary_roles')
    op.drop_column('nodes', 'pending_roles')
    op.drop_column('nodes', 'roles')
