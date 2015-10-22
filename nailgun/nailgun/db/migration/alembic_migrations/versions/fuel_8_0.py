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

"""Fuel 8.0

Revision ID: 43b2cb64dae6
Revises: 1e50a4903910
Create Date: 2015-10-15 17:20:11.132934

"""

# revision identifiers, used by Alembic.
revision = '43b2cb64dae6'
down_revision = '1e50a4903910'

from alembic import op
from oslo_serialization import jsonutils
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import upgrade_enum


release_states_old = (
    'available',
    'unavailable',
)
release_states_new = (
    'available',
    'unavailable',
    'manageonly',
)

task_statuses_old = (
    'ready',
    'running',
    'error'
)

task_statuses_new = task_statuses_old + (
    'pending',
)


task_names_old = (
    'super',
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
    'remove_stats_user',
)
task_names_new = task_names_old + (
    'update_dnsmasq',
)


node_errors_old = (
    'deploy',
    'provision',
    'deletion',
)
node_errors_new = (
    'deploy',
    'provision',
    'deletion',
    'discover',
)


def upgrade():
    create_components_table()
    create_release_components_table()
    upgrade_nodegroups_name_cluster_constraint()
    upgrade_release_state()
    task_statuses_upgrade()
    task_names_upgrade()
    add_node_discover_error_upgrade()
    upgrade_neutron_parameters()


def downgrade():
    downgrade_neutron_parameters()
    add_node_discover_error_downgrade()
    task_names_downgrade()
    task_statuses_downgrade()
    downgrade_release_state()

    op.drop_constraint('_name_cluster_uc', 'nodegroups',)
    op.drop_table('release_components')
    op.drop_table('components')
    drop_enum('component_types')


def upgrade_release_state():
    connection = op.get_bind()
    op.drop_column('releases', 'is_deployable')

    upgrade_enum(
        'releases',
        'state',
        'release_state',
        release_states_old,
        release_states_new,
    )

    connection.execute(sa.sql.text(
        "UPDATE releases SET state='manageonly' WHERE state!='unavailable'"))


def upgrade_nodegroups_name_cluster_constraint():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT name FROM nodegroups GROUP BY name HAVING COUNT(*) >= 2")
    update_query = sa.sql.text(
        "UPDATE nodegroups SET name = :name WHERE id = :ng_id")
    ng_query = sa.sql.text(
        "SELECT id, name FROM nodegroups WHERE name = :name")
    for name in connection.execute(select_query):
        for i, data in enumerate(connection.execute(ng_query, name=name[0])):
            connection.execute(
                update_query,
                ng_id=data[0], name="{0}_{1}".format(data[1], i))

    op.create_unique_constraint(
        '_name_cluster_uc',
        'nodegroups',
        [
            'cluster_id',
            'name'
        ]
    )


def create_components_table():
    op.create_table('components',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(), nullable=False),
                    sa.Column('type', sa.Enum('hypervisor', 'network',
                                              'storage', 'additional_service',
                                              name='component_types'),
                              nullable=False),
                    sa.Column('hypervisors', psql.ARRAY(sa.String()),
                              server_default='{}', nullable=False),
                    sa.Column('networks', psql.ARRAY(sa.String()),
                              server_default='{}', nullable=False),
                    sa.Column('storages', psql.ARRAY(sa.String()),
                              server_default='{}', nullable=False),
                    sa.Column('additional_services', psql.ARRAY(sa.String()),
                              server_default='{}', nullable=False),
                    sa.Column('plugin_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(
                        ['plugin_id'], ['plugins.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name', 'type',
                                        name='_component_name_type_uc')
                    )


def create_release_components_table():
    op.create_table('release_components',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('release_id', sa.Integer(), nullable=False),
                    sa.Column('component_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(
                        ['component_id'], ['components.id'], ),
                    sa.ForeignKeyConstraint(
                        ['release_id'], ['releases.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )


def downgrade_release_state():
    connection = op.get_bind()

    connection.execute(sa.sql.text(
        "UPDATE releases SET state='available' WHERE state!='unavailable'"))
    op.add_column(
        'releases',
        sa.Column(
            'is_deployable',
            sa.Boolean(),
            nullable=False,
            server_default='true',
        )
    )

    upgrade_enum(
        'releases',
        'state',
        'release_state',
        release_states_new,
        release_states_old,
    )


def task_statuses_upgrade():
    upgrade_enum('tasks', 'status', 'task_status',
                 task_statuses_old, task_statuses_new)


def task_statuses_downgrade():
    upgrade_enum('tasks', 'status', 'task_status',
                 task_statuses_new, task_statuses_old)


def task_names_upgrade():
    upgrade_enum(
        "tasks",
        "name",
        "task_name",
        task_names_old,
        task_names_new
    )


def task_names_downgrade():
    upgrade_enum(
        "tasks",
        "name",
        "task_name",
        task_names_new,
        task_names_old
    )


def add_node_discover_error_upgrade():
    upgrade_enum(
        "nodes",
        "error_type",
        "node_error_type",
        node_errors_old,
        node_errors_new
    )


def add_node_discover_error_downgrade():
    upgrade_enum(
        "nodes",
        "error_type",
        "node_error_type",
        node_errors_new,
        node_errors_old
    )


def upgrade_neutron_parameters():
    connection = op.get_bind()

    op.add_column(
        'neutron_config',
        sa.Column('internal_name', sa.String(length=50), nullable=True))
    op.add_column(
        'neutron_config',
        sa.Column('floating_name', sa.String(length=50), nullable=True))

    # net04 and net04_ext are names that were previously hardcoded,
    # so let's use them for backward compatibility reason
    connection.execute(sa.sql.text("""
        UPDATE neutron_config
            SET internal_name = 'net04',
                floating_name = 'net04_ext'
        """))

    op.alter_column('neutron_config', 'internal_name', nullable=False)
    op.alter_column('neutron_config', 'floating_name', nullable=False)

    # usually, we don't allow to create new clusters using old releases,
    # but let's patch old releases just in case
    select_query = sa.sql.text("SELECT id, networks_metadata FROM releases")

    for id_, networks_metadata in connection.execute(select_query):
        networks_metadata = jsonutils.loads(networks_metadata)

        if networks_metadata.get('neutron', {}).get('config') is not None:
            networks_metadata['neutron']['config'].update({
                'internal_name': 'net04',
                'floating_name': 'net04_ext',
            })

            connection.execute(
                sa.sql.text("""
                    UPDATE releases
                        SET networks_metadata = :networks_metadata
                        WHERE id = :id
                """),
                id=id_,
                networks_metadata=jsonutils.dumps(networks_metadata))


def downgrade_neutron_parameters():
    op.drop_column('neutron_config', 'floating_name')
    op.drop_column('neutron_config', 'internal_name')
