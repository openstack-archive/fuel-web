#    Copyright 2014 Mirantis, Inc.
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

"""fuel_6_0

Revision ID: 1b1d4016375d
Revises: 52924111f7d8
Create Date: 2014-09-18 12:44:28.327312

"""

# revision identifiers, used by Alembic.
revision = '1b1d4016375d'
down_revision = '52924111f7d8'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from nailgun.utils.migration import upgrade_release_fill_orchestrator_data
from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import upgrade_release_set_deployable_false


def upgrade():
    """Upgrade schema and then upgrade data."""
    upgrade_schema()
    upgrade_data()


def downgrade():
    """Downgrade data and then downgrade schema."""
    downgrade_data()
    downgrade_schema()


def upgrade_schema():
    op.add_column(
        'releases',
        sa.Column(
            'is_deployable',
            sa.Boolean(),
            nullable=False,
            server_default='true',
        )
    )
    op.create_table(
        'plugin_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plugin', sa.String(length=150), nullable=True),
        sa.Column('record_type', sa.Enum(
            'role',
            'pending_role',
            'volume',
            'cluster_attribute',
            name='record_type'
        ), nullable=False),
        sa.Column('data', postgresql.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def upgrade_data():
    connection = op.get_bind()

    # do not deploy 5.0.x series
    upgrade_release_set_deployable_false(
        connection, ['2014.1', '2014.1.1-5.0.1', '2014.1.1-5.0.2'])

    # In Fuel 5.x default releases do not have filled orchestrator_data,
    # and defaults one have been used. In Fuel 6.0 we're going to change
    # default paths, so we need to keep them for old releases explicitly.
    #
    # NOTE: all release versions in Fuel 5.x starts with "2014.1"
    upgrade_release_fill_orchestrator_data(connection, ['2014.1%'])


def downgrade_schema():
    op.drop_table('plugin_records')
    drop_enum('record_type')
    op.drop_column('releases', 'is_deployable')


def downgrade_data():
    pass
