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

import sqlalchemy as sa

from alembic import op
from sqlalchemy.sql import text
from oslo.serialization import jsonutils

from nailgun.db.sqlalchemy.models import fields
from nailgun.extensions.consts import extensions_migration_buffer_table_name


def upgrade():
    connection = op.get_bind()

    op.create_foreign_key(
        None, 'network_groups', 'nodegroups', ['group_id'], ['id'])
    op.create_foreign_key(
        None, 'nodes', 'nodegroups', ['group_id'], ['id'])
    op.alter_column(
        'oswl_stats', 'resource_checksum', existing_type=sa.TEXT(),
        nullable=False)
    op.create_unique_constraint(
        None, 'oswl_stats', ['cluster_id', 'created_date', 'resource_type'])

    extend_plugin_model_upgrade()
    migrate_volumes_into_extension(connection)


def downgrade():
    op.drop_constraint(None, 'oswl_stats', type_='unique')
    op.alter_column(
        'oswl_stats', 'resource_checksum', existing_type=sa.TEXT(),
        nullable=True)
    op.drop_constraint(None, 'nodes', type_='foreignkey')
    op.drop_constraint(None, 'network_groups', type_='foreignkey')

    extend_plugin_model_downgrade()

    op.drop_table(extensions_migration_buffer_table_name)
    op.add_column(
        'node_attributes',
        sa.Column('volumes', fields.JSON(), nullable=True))


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


def extend_plugin_model_downgrade():
    op.drop_column('plugins', 'tasks')
    op.drop_column('plugins', 'deployment_tasks')
    op.drop_column('plugins', 'roles_metadata')
    op.drop_column('plugins', 'volumes_metadata')
    op.drop_column('plugins', 'attributes_metadata')


def migrate_volumes_into_extension(connection):
    """Migrate data into intermidiate table, from
    which specific extensions will be able to retrieve
    the data. It allows us not to hardcode extension's
    tables in core migrations.
    """
    # Create migration buffer table for extensions
    op.create_table(
        extensions_migration_buffer_table_name,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('extension_name', sa.Text()),
        sa.Column('data', fields.JSON()),
        sa.PrimaryKeyConstraint('id'))

    select_query = text("SELECT node_id, volumes FROM node_attributes")
    insert_query = text(
        "INSERT INTO {0} (extension_name, data)"
        "VALUES (:extension_name, :data)".format(
            extensions_migration_buffer_table_name))

    # Fill in the buffer
    for volume_attr in connection.execute(select_query):
        node_id = volume_attr[0]
        volumes = volume_attr[1]
        connection.execute(
            insert_query,
            data=jsonutils.dumps({'node_id': node_id, 'volumes': volumes}),
            extension_name='volume_manager')

    # Drop the table after the data were migrated
    op.drop_column('node_attributes', 'volumes')
