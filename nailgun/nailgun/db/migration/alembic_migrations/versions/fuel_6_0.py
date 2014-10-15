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

from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import dump_master_node_settings
from nailgun.utils.migration import upgrade_release_fill_orchestrator_data
from nailgun.utils.migration import upgrade_release_set_deployable_false

ENUMS = (
    'action_type',
)


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
    op.create_table('action_logs',
                    sa.Column('id', sa.Integer, nullable=False),
                    sa.Column(
                        'actor_id',
                        sa.String(length=64),
                        nullable=True
                    ),
                    sa.Column(
                        'action_group',
                        sa.String(length=64),
                        nullable=False
                    ),
                    sa.Column(
                        'action_name',
                        sa.String(length=64),
                        nullable=False
                    ),
                    sa.Column(
                        'action_type',
                        sa.Enum('http_request', 'nailgun_task',
                                name='action_type'),
                        nullable=False
                    ),
                    sa.Column(
                        'start_timestamp',
                        sa.DateTime,
                        nullable=False
                    ),
                    sa.Column(
                        'end_timestamp',
                        sa.DateTime,
                        nullable=True
                    ),
                    sa.Column(
                        'is_sent',
                        sa.Boolean,
                        default=False
                    ),
                    sa.Column(
                        'additional_info',
                        JSON(),
                        nullable=False
                    ),
                    sa.Column(
                        'cluster_id',
                        sa.Integer,
                        nullable=True
                    ),
                    sa.Column(
                        'task_uuid',
                        sa.String(36),
                        nullable=True
                    ),
                    sa.PrimaryKeyConstraint('id'))
    op.create_table('master_node_settings',
                    sa.Column('id', sa.Integer, nullable=False),
                    sa.Column(
                        'master_node_uid',
                        sa.String(36),
                        nullable=False
                    ),
                    sa.Column(
                        'settings',
                        JSON(),
                        default={}
                    ),
                    sa.PrimaryKeyConstraint('id'))
    op.create_table(
        'plugins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('description', sa.String(length=400), nullable=True),
        sa.Column('releases', postgresql.JSON(), nullable=True),
        sa.Column('types', postgresql.JSON(), nullable=True),
        sa.Column('package_version', sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'version', name='_name_version_unique')
    )
    op.create_table(
        'cluster_plugins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plugin_id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ),
        sa.ForeignKeyConstraint(
            ['plugin_id'], ['plugins.id'], ondelete='CASCADE'),
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

    # generate uid for master node and insert
    # it into master_node_settings table
    dump_master_node_settings(connection)


def downgrade_schema():
    op.drop_column('releases', 'is_deployable')
    op.drop_table('action_logs')
    op.drop_table('master_node_settings')
    map(drop_enum, ENUMS)
    op.drop_table('cluster_plugins')
    op.drop_table('plugins')


def downgrade_data():
    pass
