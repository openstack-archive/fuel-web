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

"""Fuel 9.1

Revision ID: f2314e5d63c9
Revises: 675105097a69
Create Date: 2016-06-24 13:23:33.235613

"""

from alembic import op
from distutils.version import StrictVersion
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun.db.sqlalchemy.models import fields
from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import upgrade_enum


# revision identifiers, used by Alembic.
revision = 'f2314e5d63c9'
down_revision = '675105097a69'

rule_to_pick_bootdisk = [
    {'type': 'exclude_disks_by_name',
     'regex': '^nvme',
     'description': 'NVMe drives should be skipped as accessing such drives '
                    'during the boot typically requires using UEFI which is '
                    'still not supported by fuel-agent (it always installs '
                    'BIOS variant of  grub). '
                    'grub bug (http://savannah.gnu.org/bugs/?41883)'},
    {'type': 'pick_root_disk_if_disk_name_match',
     'regex': '^md',
     'root_mount': '/',
     'description': 'If we have /root on fake raid, then /boot partition '
                    'should land on to it too. We can\'t proceed with '
                    'grub-install otherwise.'}
]


def upgrade():
    upgrade_cluster_attributes()
    upgrade_release_with_rules_to_pick_bootable_disk()
    upgrade_task_model()
    upgrade_deployment_graphs_attributes()
    upgrade_orchestrator_task_types()
    upgrade_node_error_type()
    upgrade_deployment_history_summary()
    upgrade_add_task_start_end_time()
    fix_deployment_history_constraint()
    upgrade_deployment_sequences()
    upgrade_release_state()
    upgrade_attributes_metadata()
    upgrade_networks_metadata()


def downgrade():
    downgrade_deployment_sequences()
    downgrade_add_task_start_end_time()
    downgrade_cluster_attributes()
    downgrade_deployment_history_summary()
    downgrade_node_error_type()
    downgrade_orchestrator_task_types()
    downgrade_deployment_graphs_attributes()
    downgrade_task_model()
    downgrade_release_with_rules_to_pick_bootable_disk()


def upgrade_release_with_rules_to_pick_bootable_disk():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, volumes_metadata FROM releases "
        "WHERE volumes_metadata IS NOT NULL")
    update_query = sa.sql.text(
        "UPDATE releases SET volumes_metadata = :volumes_metadata "
        "WHERE id = :id")

    for id, volumes_metadata in connection.execute(select_query):
        volumes_metadata = jsonutils.loads(volumes_metadata)

        volumes_metadata['rule_to_pick_boot_disk'] = rule_to_pick_bootdisk

        connection.execute(
            update_query,
            id=id,
            volumes_metadata=jsonutils.dumps(volumes_metadata),
        )


def upgrade_deployment_history_summary():
    op.add_column(
        'deployment_history',
        sa.Column(
            'summary',
            fields.JSON(),
            nullable=True,
            server_default='{}'
        )
    )


def downgrade_release_with_rules_to_pick_bootable_disk():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, volumes_metadata FROM releases "
        "WHERE volumes_metadata IS NOT NULL")
    update_query = sa.sql.text(
        "UPDATE releases SET volumes_metadata = :volumes_metadata "
        "WHERE id = :id")

    for id, volumes_metadata in connection.execute(select_query):
        volumes_metadata = jsonutils.loads(volumes_metadata)
        rule = volumes_metadata.pop('rule_to_pick_boot_disk', None)
        if rule is not None:
            connection.execute(
                update_query,
                id=id,
                volumes_metadata=jsonutils.dumps(volumes_metadata),
            )


def upgrade_task_model():
    op.add_column(
        'tasks',
        sa.Column('graph_type', sa.String(255), nullable=True)
    )
    op.add_column(
        'tasks',
        sa.Column(
            'dry_run', sa.Boolean(), nullable=False, server_default='false'
        )
    )


def downgrade_task_model():
    op.drop_column('tasks', 'dry_run')
    op.drop_column('tasks', 'graph_type')


def upgrade_deployment_graphs_attributes():
    op.add_column(
        'deployment_graphs',
        sa.Column(
            'node_filter',
            sa.String(4096),
            nullable=True
        )
    )
    op.add_column(
        'deployment_graphs',
        sa.Column(
            'on_success',
            fields.JSON(),
            nullable=True
        )
    )
    op.add_column(
        'deployment_graphs',
        sa.Column(
            'on_error',
            fields.JSON(),
            nullable=True
        )
    )
    op.add_column(
        'deployment_graphs',
        sa.Column(
            'on_stop',
            fields.JSON(),
            nullable=True
        )
    )


def downgrade_deployment_graphs_attributes():
    op.drop_column('deployment_graphs', 'node_filter')
    op.drop_column('deployment_graphs', 'on_success')
    op.drop_column('deployment_graphs', 'on_error')
    op.drop_column('deployment_graphs', 'on_stop')


orchestrator_task_types_old = (
    'puppet',
    'shell',
    'sync',
    'upload_file',
    'group',
    'stage',
    'skipped',
    'reboot',
    'copy_files',
    'role'
)


orchestrator_task_types_new = orchestrator_task_types_old + (
    'master_shell',
    'move_to_bootstrap',
    'erase_node'
)


def upgrade_orchestrator_task_types():
    upgrade_enum(
        'deployment_graph_tasks',
        'type',
        'deployment_graph_tasks_type',
        orchestrator_task_types_old,
        orchestrator_task_types_new
    )


def downgrade_orchestrator_task_types():
    upgrade_enum(
        'deployment_graph_tasks',
        'type',
        'deployment_graph_tasks_type',
        orchestrator_task_types_new,
        orchestrator_task_types_old
    )


node_error_types_old = (
    'deploy',
    'provision',
    'deletion',
    'discover',
    'stop_deployment'
)


def upgrade_node_error_type():
    op.alter_column('nodes', 'error_type', type_=sa.String(100))
    drop_enum('node_error_type')


def downgrade_node_error_type():
    enum_type = sa.Enum(*node_error_types_old, name='node_error_type')
    enum_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        u'ALTER TABLE nodes ALTER COLUMN error_type TYPE  node_error_type'
        u' USING error_type::text::node_error_type'
    )


def downgrade_deployment_history_summary():
    op.drop_column('deployment_history', 'summary')


def upgrade_cluster_attributes():
    select_query = sa.sql.text(
        "SELECT id, replaced_deployment_info FROM clusters"
        " WHERE replaced_deployment_info IS NOT NULL"
    )

    update_query = sa.sql.text(
        "UPDATE clusters SET replaced_deployment_info = :info "
        "WHERE id = :id"
    )

    connection = op.get_bind()

    for cluster_id, info in connection.execute(select_query):
        info = jsonutils.loads(info)
        if isinstance(info, dict):
            continue

        # replaced_deployment_info does not contain value since 5.1
        # replaced_deployment_info was moved from cluster to nodes table
        connection.execute(
            update_query,
            id=cluster_id,
            info=jsonutils.dumps({}),
        )


def downgrade_cluster_attributes():
    select_query = sa.sql.text(
        "SELECT id, replaced_deployment_info FROM clusters"
        " WHERE replaced_deployment_info IS NOT NULL"
    )

    update_query = sa.sql.text(
        "UPDATE clusters SET replaced_deployment_info = :info "
        "WHERE id = :id"
    )

    connection = op.get_bind()

    for cluster_id, info in connection.execute(select_query):
        info = jsonutils.loads(info)

        if isinstance(info, list):
            continue

        connection.execute(
            update_query,
            id=cluster_id,
            info=jsonutils.dumps([]),
        )


def upgrade_add_task_start_end_time():
    op.add_column(
        'tasks',
        sa.Column(
            'time_start',
            sa.TIMESTAMP(),
            nullable=True,
        )
    )

    op.add_column(
        'tasks',
        sa.Column(
            'time_end',
            sa.TIMESTAMP(),
            nullable=True,
        )
    )


def downgrade_add_task_start_end_time():
    op.drop_column('tasks', 'time_start')
    op.drop_column('tasks', 'time_end')


def fix_deployment_history_constraint():
    # only recreate deployment_history_task_id_fkey with valid properties
    op.drop_constraint(
        'deployment_history_task_id_fkey',
        'deployment_history',
        type_='foreignkey'
    )

    op.create_foreign_key(
        "deployment_history_task_id_fkey",
        "deployment_history", "tasks",
        ["task_id"], ["id"], ondelete="CASCADE"
    )


def upgrade_deployment_sequences():
    op.create_table(
        'deployment_sequences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('release_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('graphs', fields.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id']),
        sa.UniqueConstraint('release_id', 'name')
    )


def downgrade_deployment_sequences():
    op.drop_table('deployment_sequences')


def upgrade_release_state():
    select_query = sa.sql.text(
        "SELECT id, version FROM releases WHERE state='available'"
    )

    update_query = sa.sql.text(
        "UPDATE releases SET state='manageonly' WHERE id IN :ids"
    )

    connection = op.get_bind()

    ids = []
    for id_, version in connection.execute(select_query):
        try:
            version = version.split('-')[1]
        except IndexError:
            continue

        if StrictVersion(version) < StrictVersion('9.0'):
            ids.append(id_)

    if ids:
        connection.execute(update_query, ids=tuple(ids))


ATTRIBUTES_PING = {
    'description': ('Uncheck this box if the public gateway will not be '
                    'available or will not respond to ICMP requests to '
                    'the deployed cluster. If unchecked, the controllers '
                    'will not take public gateway availability into account '
                    'as part of the cluster health.  If the cluster will not '
                    'have internet access, you will need to make sure to '
                    'provide proper offline mirrors for the deployment to '
                    'succeed.'),
    'group': 'network',
    'label': 'Public Gateway is Available',
    'type': 'checkbox',
    'value': True,
    'weight': 50
}

ATTRIBUTES_S3 = {
    'description': ('This allows to authenticate S3 requests basing on '
                    'EC2/S3 credentials managed by Keystone. Please note '
                    'that enabling the integration will increase the '
                    'latency of S3 requests as well as load on Keystone '
                    'service. Please consult with Mirantis Technical '
                    'Bulletin 27 and Mirantis Support on mitigating the '
                    'risks related with load.'),
    'label': 'Enable S3 API Authentication via Keystone in Ceph RadosGW',
    'restrictions': [{
        'action': 'hide',
        'condition': 'settings:storage.objects_ceph.value == false'
    }],
    'type': 'checkbox',
    'value': False,
    'weight': 82
}

KERNEL_CMDLINE1 = ("console=tty0 net.ifnames=0 biosdevname=0 "
                   "rootdelay=90 nomodeset")
KERNEL_CMDLINE2 = ("console=tty0 net.ifnames=1 biosdevname=0 "
                   "rootdelay=90 nomodeset")


def upgrade_attributes_metadata():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, attributes_metadata FROM releases "
        "WHERE attributes_metadata IS NOT NULL")

    update_query = sa.sql.text(
        "UPDATE releases SET attributes_metadata = :attributes_metadata "
        "WHERE id = :id")

    for id, attrs in connection.execute(select_query):
        attrs = jsonutils.loads(attrs)
        editable = attrs.setdefault('editable', {})
        storage = editable.setdefault('storage', {})
        storage.setdefault('auth_s3_keystone_ceph', ATTRIBUTES_S3)

        common = editable.setdefault('common', {})
        common.setdefault('run_ping_checker', ATTRIBUTES_PING)

        kernel_params = editable.setdefault('kernel_params', {})
        kernel = kernel_params.setdefault('kernel', {})
        if kernel.get('value') == KERNEL_CMDLINE1:
            kernel['value'] = KERNEL_CMDLINE2

        connection.execute(
            update_query,
            id=id,
            attributes_metadata=jsonutils.dumps(attrs))


def upgrade_networks_metadata():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, networks_metadata FROM releases "
        "WHERE networks_metadata IS NOT NULL")

    update_query = sa.sql.text(
        "UPDATE releases SET networks_metadata = :networks_metadata "
        "WHERE id = :id")

    for id, nets in connection.execute(select_query):
        nets = jsonutils.loads(nets)
        if 'dpdk_drivers' in nets and 'igb_uio' in nets['dpdk_drivers']:
            igb_uio = nets['dpdk_drivers']['igb_uio']
            if igb_uio and '8086:10f8' not in igb_uio:
                igb_uio.append('8086:10f8')

        connection.execute(
            update_query,
            id=id,
            networks_metadata=jsonutils.dumps(nets))
