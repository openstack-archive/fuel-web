#    Copyright 2016 Mirantis, Inc.
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

"""Fuel 9.0.1

Revision ID: 675105097a69
Revises: 11a9adc6d36a
Create Date: 2016-04-28 22:23:40.895589

"""

from alembic import op
import sqlalchemy as sa

from nailgun.db.sqlalchemy.models import fields
from nailgun.utils.migration import upgrade_enum


# revision identifiers, used by Alembic.
revision = '675105097a69'
down_revision = '11a9adc6d36a'


def upgrade():
    upgrade_deployment_history()
    upgrade_transaction_names()
    upgrade_clusters_replaced_info_wrong_default()
    upgrade_tasks_snapshot()
    upgrade_node_error_msg_to_allow_long_error_msg()


def downgrade():
    downgrade_tasks_snapshot()
    downgrade_clusters_replaced_info_wrong_default()
    downgrade_transaction_names()
    downgrade_deployment_history()
    downgrade_node_error_msg_to_allow_long_error_msg()


def upgrade_deployment_history():
    op.create_index('deployment_history_task_name_status_idx',
                    'deployment_history',
                    ['deployment_graph_task_name', 'status'])


def downgrade_deployment_history():
    op.drop_index('deployment_history_task_name_status_idx',
                  'deployment_history')


def upgrade_clusters_replaced_info_wrong_default():
    connection = op.get_bind()
    update_query = sa.sql.text(
        "UPDATE clusters SET replaced_deployment_info = '[]' "
        "WHERE replaced_deployment_info = '{}'")
    connection.execute(update_query)


def downgrade_clusters_replaced_info_wrong_default():
    connection = op.get_bind()
    update_query = sa.sql.text(
        "UPDATE clusters SET replaced_deployment_info = '{}' "
        "WHERE replaced_deployment_info = '[]'")
    connection.execute(update_query)


def upgrade_tasks_snapshot():
    op.add_column(
        'tasks',
        sa.Column(
            'tasks_snapshot',
            fields.JSON(),
            nullable=True
        )
    )


def downgrade_tasks_snapshot():
    op.drop_column('tasks', 'tasks_snapshot')


transaction_names_old = (
    'super',

    # Cluster changes
    # For deployment supertask, it contains
    # two subtasks deployment and provision
    'deploy',
    'deployment',
    'provision',
    'stop_deployment',
    'reset_environment',
    'update',
    'spawn_vms',

    'node_deletion',
    'cluster_deletion',
    'remove_images',
    'check_before_deployment',

    # network
    'check_networks',
    'verify_networks',
    'check_dhcp',
    'verify_network_connectivity',
    'multicast_verification',
    'check_repo_availability',
    'check_repo_availability_with_setup',

    # dump
    'dump',

    'capacity_log',

    # statistics
    'create_stats_user',
    'remove_stats_user',

    # setup dhcp via dnsmasq for multi-node-groups
    'update_dnsmasq'
)


transaction_names_new = transaction_names_old + ('dry_run_deployment',)


def upgrade_transaction_names():
    upgrade_enum(
        'tasks',
        'name',
        'task_name',
        transaction_names_old,
        transaction_names_new
    )


def upgrade_node_error_msg_to_allow_long_error_msg():
    op.alter_column(table_name='nodes',
                    column_name='error_msg',
                    type_=sa.Text)


def downgrade_transaction_names():
    upgrade_enum(
        'tasks',
        'name',
        'task_name',
        transaction_names_new,
        transaction_names_old
    )


def downgrade_node_error_msg_to_allow_long_error_msg():
    connection = op.get_bind()
    connection.execute(sa.text('''
UPDATE nodes SET error_msg = substring(error_msg for 255);
'''))
    op.alter_column(table_name='nodes',
                    column_name='error_msg',
                    type_=sa.String(255))
