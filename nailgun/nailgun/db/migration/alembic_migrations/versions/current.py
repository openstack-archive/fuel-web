"""Changes before merge

Revision ID: 4f21f21e2672
Revises: 3540e7a3ba1e
Create Date: 2014-02-12 18:16:55.630914

"""

# revision identifiers, used by Alembic.
revision = '4f21f21e2672'
down_revision = '3540e7a3ba1e'

from alembic import op
import sqlalchemy as sa

from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.fields import LowercaseString


old_cluster_status_options = (
    'new',
    'deployment',
    'operational',
    'error',
    'remove'
)
new_cluster_status_options = sorted(
    old_cluster_status_options + ('stopped',)
)

old_task_names_options = (
    'super',
    'deploy',
    'deployment',
    'provision',
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
new_task_names_options = sorted(
    old_task_names_options + (
        'stop_deployment',
        'reset_environment'
    )
)

old_cluster_changes = (
    'networks',
    'attributes',
    'disks'
)
new_cluster_changes = sorted(
    old_cluster_changes + ('interfaces',)
)


def upgrade_enum(table, column_name, enum_name, old_options, new_options):
    old_type = sa.Enum(*old_options, name=enum_name)
    new_type = sa.Enum(*new_options, name=enum_name)
    tmp_type = sa.Enum(*new_options, name="_" + enum_name)
    # Create a tempoary type, convert and drop the "old" type
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        u'ALTER TABLE {0} ALTER COLUMN {1} TYPE _{2}'
        u' USING {1}::text::_{2}'.format(
            table,
            column_name,
            enum_name
        )
    )
    old_type.drop(op.get_bind(), checkfirst=False)
    # Create and convert to the "new" type
    new_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        u'ALTER TABLE {0} ALTER COLUMN {1} TYPE {2}'
        u' USING {1}::text::{2}'.format(
            table,
            column_name,
            enum_name
        )
    )
    tmp_type.drop(op.get_bind(), checkfirst=False)
    ### end Alembic commands ###


def drop_enum(name):
    op.execute(
        u'DROP TYPE {0}'.format(name)
    )


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('global_parameters')
    op.alter_column(
        'network_groups',
        'netmask',
        existing_type=sa.VARCHAR(length=25),
        nullable=True
    )
    op.drop_table('plugins')
    op.drop_table('allowed_networks')
    op.add_column(
        'network_groups',
        sa.Column(
            'meta',
            JSON(),
            nullable=True
        )
    )
    op.add_column(
        'node_nic_interfaces',
        sa.Column(
            'parent_id',
            sa.Integer(),
            nullable=True
        )
    )
    op.rename_table(
        'net_assignments',
        'net_nic_assignments'
    )
    op.create_table(
        'node_bond_interfaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=32), nullable=False),
        sa.Column('mac', LowercaseString(length=17), nullable=True),
        sa.Column('state', sa.String(length=25), nullable=True),
        sa.Column('flags', JSON(), nullable=True),
        sa.Column(
            'mode',
            sa.Enum(
                'active-backup',
                'balance-slb',
                'lacp-balance-tcp',
                name='bond_mode'
            ),
            nullable=False
        ),
        sa.ForeignKeyConstraint(
            ['node_id'],
            ['nodes.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'net_bond_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('network_id', sa.Integer(), nullable=False),
        sa.Column('bond_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['bond_id'],
            ['node_bond_interfaces.id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['network_id'],
            ['network_groups.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )

    # CLUSTER STATUS ENUM UPGRADE
    upgrade_enum(
        "clusters",                  # table
        "status",                    # column
        "cluster_status",            # ENUM name
        old_cluster_status_options,  # old options
        new_cluster_status_options   # new options
    )

    # TASK NAME ENUM UPGRADE
    upgrade_enum(
        "tasks",                     # table
        "name",                      # column
        "task_name",                 # ENUM name
        old_task_names_options,      # old options
        new_task_names_options       # new options
    )

    op.add_column('nodes', sa.Column(
        'agent_checksum', sa.String(40), nullable=True
    ))

    op.add_column('nodes', sa.Column(
        'uuid', sa.String(length=36), nullable=False
    ))
    op.create_unique_constraint("uq_node_uuid", "nodes", ["uuid"])

    # CLUSTER CHANGES ENUM UPGRADE
    upgrade_enum(
        "cluster_changes",           # table
        "name",                      # column
        "possible_changes",          # ENUM name
        old_cluster_changes,         # old changes
        new_cluster_changes          # new changes
    )

    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    # CLUSTER CHANGES ENUM DOWNGRADE
    upgrade_enum(
        "cluster_changes",           # table
        "name",                      # column
        "possible_changes",          # ENUM name
        new_cluster_changes,         # new changes
        old_cluster_changes          # old changes
    )

    op.alter_column(
        'network_groups',
        'netmask',
        existing_type=sa.VARCHAR(length=25),
        nullable=False
    )
    op.create_table(
        'global_parameters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parameters', JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.drop_column('network_groups', 'meta')
    op.create_table(
        'allowed_networks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('network_id', sa.Integer(), nullable=False),
        sa.Column('interface_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['interface_id'],
            ['node_nic_interfaces.id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['network_id'],
            ['network_groups.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    drop_enum('plugin_type')
    op.create_table(
        'plugins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column(
            'type',
            sa.Enum('nailgun', 'fuel', name='plugin_type'),
            nullable=False
        ),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('state', sa.String(length=128), nullable=False),
        sa.Column('version', sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    # CLUSTER STATUS ENUM DOWNGRADE
    upgrade_enum(
        "clusters",                  # table
        "status",                    # column
        "cluster_status",            # ENUM name
        new_cluster_status_options,  # old options
        old_cluster_status_options   # new options
    )

    # TASK NAME ENUM DOWNGRADE
    upgrade_enum(
        "tasks",                     # table
        "name",                      # column
        "task_name",                 # ENUM name
        new_task_names_options,      # old options
        old_task_names_options       # new options
    )

    op.drop_column(
        u'node_nic_interfaces',
        'parent_id'
    )
    op.rename_table(
        'net_nic_assignments',
        'net_assignments'
    )
    op.drop_table('net_bond_assignments')
    op.drop_table('node_bond_interfaces')
    drop_enum('bond_mode')
    op.drop_column('nodes', 'agent_checksum')
    op.drop_column('nodes', 'uuid')
    ### end Alembic commands ###
