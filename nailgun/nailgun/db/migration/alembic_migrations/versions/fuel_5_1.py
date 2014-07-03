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

"""fuel_5_1

Revision ID: 52924111f7d8
Revises: 1398619bdf8c
Create Date: 2014-06-09 13:25:25.773543
"""

# revision identifiers, used by Alembic.

revision = '52924111f7d8'
down_revision = '1398619bdf8c'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from nailgun import consts
from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import upgrade_enum


cluster_changes_old = (
    'networks',
    'attributes',
    'disks'
)
cluster_changes_new = consts.CLUSTER_CHANGES


old_task_names_options = (
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
    'redhat_setup',
    'redhat_check_credentials',
    'redhat_check_licenses',
    'redhat_download_release',
    'redhat_update_cobbler_profile',
    'dump',
    'capacity_log'
)

new_task_names_options = consts.TASK_NAMES


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    upgrade_enum(
        "cluster_changes",          # table
        "name",                     # column
        "possible_changes",         # ENUM name
        cluster_changes_old,        # old options
        cluster_changes_new         # new options
    )

    # TASK NAME ENUM UPGRADE
    upgrade_enum(
        "tasks",                     # table
        "name",                      # column
        "task_name",                 # ENUM name
        old_task_names_options,      # old options
        new_task_names_options       # new options
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
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('plugin_records')
    drop_enum('record_type')

    upgrade_enum(
        "cluster_changes",          # table
        "name",                     # column
        "possible_changes",         # ENUM name
        cluster_changes_new,        # new options
        cluster_changes_old,        # old options
    )

    # TASK NAME ENUM DOWNGRADE
    upgrade_enum(
        "tasks",                     # table
        "name",                      # column
        "task_name",                 # ENUM name
        new_task_names_options,      # old options
        old_task_names_options       # new options
    )

    ### end Alembic commands ###
