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

from alembic import op
from nailgun.db.sqlalchemy.models import fields
from oslo.serialization import jsonutils

from nailgun.db.sqlalchemy.models import fields
from nailgun.extensions.consts import extensions_migration_buffer_table_name
from nailgun.utils.migration import drop_enum


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
    migrate_volumes_into_extension_upgrade()
    networking_templates_upgrade()


def downgrade():
    networking_templates_downgrade()
    migrate_volumes_into_extension_downgrade()
    extend_plugin_model_downgrade()
    extend_ip_addrs_model_downgrade()
    extend_node_model_downgrade()

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


def extend_node_model_downgrade():
    op.drop_column('node_bond_interfaces', 'offloading_modes')
    op.drop_column('node_nic_interfaces', 'offloading_modes')


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


def networking_templates_upgrade():
    op.add_column(
        'networking_configs',
        sa.Column(
            'configuration_template', fields.JSON(),
            nullable=True, server_default='{}')
    )
    op.add_column(
        'nodes',
        sa.Column(
            'network_template', fields.JSON(), nullable=True,
            server_default='{}')
    )


def networking_templates_downgrade():
    op.drop_column('nodes', 'network_template')
    op.drop_column('networking_configs', 'configuration_template')


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
