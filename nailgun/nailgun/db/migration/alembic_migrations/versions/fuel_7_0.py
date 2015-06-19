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

from nailgun.utils.migration import upgrade_network_groups_metadata_6_1_to_7_0
from nailgun.db.sqlalchemy.models import fields


def upgrade():
    upgrade_schema()
    upgrade_data()


def downgrade():
    downgrade_schema()
    downgrade_data()


def upgrade_schema():
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
    extend_releases_model_upgrade()


def downgrade_schema():
    op.drop_constraint(None, 'oswl_stats', type_='unique')
    op.alter_column(
        'oswl_stats', 'resource_checksum', existing_type=sa.TEXT(),
        nullable=True)
    op.drop_constraint(None, 'nodes', type_='foreignkey')
    op.drop_constraint(None, 'network_groups', type_='foreignkey')

    extend_plugin_model_downgrade()
    extend_releases_model_downgrade()


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


def extend_releases_model_upgrade():
    op.add_column(
        'releases',
        sa.Column(
            'network_roles_metadata',
            fields.JSON(),
            server_default='{}'))


def extend_plugin_model_downgrade():
    op.drop_column('plugins', 'tasks')
    op.drop_column('plugins', 'deployment_tasks')
    op.drop_column('plugins', 'roles_metadata')
    op.drop_column('plugins', 'volumes_metadata')
    op.drop_column('plugins', 'attributes_metadata')


def extend_releases_model_downgrade():
    op.drop_column('releases', 'network_roles_metadata')


def upgrade_data():
    connection = op.get_bind()
    upgrade_network_groups_metadata_6_1_to_7_0(connection)


def downgrade_data():
    pass
