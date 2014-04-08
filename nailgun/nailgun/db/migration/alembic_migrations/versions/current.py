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

old_network_group_name = (
    'fuelweb_admin',
    'storage',
    'management',
    'public',
    'floating',
    'fixed',
    'private'
)
new_network_group_name = (
    'fuelweb_admin',
    'storage',
    'management',
    'public',
    'fixed',
    'private'
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

    op.create_table(
        'networking_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('discriminator', sa.String(length=50), nullable=True),
        sa.Column('cluster_id', sa.Integer(), nullable=True),
        sa.Column('dns_nameservers', JSON(), nullable=True),
        sa.Column('floating_ranges', JSON(), nullable=True),
        sa.ForeignKeyConstraint(['cluster_id'],
                                ['clusters.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'nova_network_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fixed_networks_cidr', sa.String(length=25), nullable=True),
        sa.Column('fixed_networks_vlan_start', sa.Integer(), nullable=True),
        sa.Column('fixed_network_size', sa.Integer(), nullable=False),
        sa.Column('fixed_networks_amount', sa.Integer(), nullable=False),
        sa.Column('net_manager',
                  sa.Enum('FlatDHCPManager',
                          'VlanManager',
                          name='net_manager'),
                  nullable=False),
        sa.ForeignKeyConstraint(['id'], ['networking_configs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'neutron_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vlan_range', JSON(), nullable=True),
        sa.Column('gre_id_range', JSON(), nullable=True),
        sa.Column('base_mac', LowercaseString(length=17), nullable=False),
        sa.Column('internal_cidr', sa.String(length=25), nullable=True),
        sa.Column('internal_gateway', sa.String(length=25), nullable=True),
        sa.Column('segmentation_type',
                  sa.Enum('vlan',
                          'gre',
                          name='segmentation_type'),
                  nullable=False),
        sa.Column('net_l23_provider',
                  sa.Enum('ovs',
                          name='net_l23_provider'),
                  nullable=False),
        sa.ForeignKeyConstraint(['id'], ['networking_configs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.add_column('nodes', sa.Column(
        'agent_checksum', sa.String(40), nullable=True
    ))

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

    # NETWORK NAME ENUM UPGRADE
    upgrade_enum(
        "network_groups",            # table
        "name",                      # column
        "network_group_name",        # ENUM name
        old_network_group_name,      # old options
        new_network_group_name       # new options
    )

    op.add_column('nodes', sa.Column(
        'uuid', sa.String(length=36), nullable=False
    ))
    op.create_unique_constraint("uq_node_uuid", "nodes", ["uuid"])

    op.drop_column(u'clusters', u'net_manager')
    op.drop_column(u'clusters', u'dns_nameservers')
    op.drop_column(u'clusters', u'net_segment_type')
    op.drop_column(u'clusters', u'net_l23_provider')
    op.drop_column(u'network_groups', u'network_size')
    op.drop_column(u'network_groups', u'amount')
    op.drop_column(u'network_groups', u'netmask')

    op.drop_table(u'neutron_configs')
    # Fuel upgrade required changes
    op.add_column('clusters',
                  sa.Column('fuel_version',
                            sa.String(length=30),
                            nullable=False))
    op.create_table(
        'release_orchestrator_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('release_id', sa.Integer(), nullable=True),
        sa.Column('repo_source', sa.Text(), nullable=True),
        sa.Column('puppet_manifests_source', sa.Text(), nullable=True),
        sa.Column('puppet_modules_source', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    # Fuel upgrade required changes
    op.drop_table('release_orchestrator_data')
    op.drop_column('clusters', 'fuel_version')

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

    op.add_column(u'network_groups',
                  sa.Column(u'amount',
                            sa.INTEGER(),
                            nullable=True))
    op.add_column(u'network_groups',
                  sa.Column(u'network_size',
                            sa.INTEGER(),
                            nullable=True))
    op.add_column(u'network_groups',
                  sa.Column(u'netmask',
                            sa.String(length=25),
                            nullable=True))
    op.add_column(u'clusters',
                  sa.Column(u'net_l23_provider',
                            sa.ENUM(u'ovs'),
                            nullable=False))
    op.add_column(u'clusters',
                  sa.Column(u'net_segment_type',
                            sa.ENUM(u'none',
                                    u'vlan',
                                    u'gre',
                                    name='net_segment_type'),
                            nullable=False))
    op.add_column(u'clusters',
                  sa.Column(u'dns_nameservers',
                            sa.TEXT(),
                            nullable=True))
    op.add_column(u'clusters',
                  sa.Column(u'net_manager',
                            sa.ENUM(u'FlatDHCPManager',
                                    u'VlanManager',
                                    name='net_manager'),
                            nullable=False))
    op.create_table(
        u'neutron_configs',
        sa.Column(u'id',
                  sa.INTEGER(),
                  server_default="nextval('neutron_configs_id_seq'::regclass)",
                  nullable=False),
        sa.Column(u'cluster_id',
                  sa.INTEGER(),
                  autoincrement=False,
                  nullable=True),
        sa.Column(u'parameters',
                  sa.TEXT(),
                  autoincrement=False,
                  nullable=True),
        sa.Column(u'L2',
                  sa.TEXT(),
                  autoincrement=False,
                  nullable=True),
        sa.Column(u'L3',
                  sa.TEXT(),
                  autoincrement=False,
                  nullable=True),
        sa.Column(u'predefined_networks',
                  sa.TEXT(),
                  autoincrement=False,
                  nullable=True),
        sa.Column(u'segmentation_type',
                  sa.ENUM(u'vlan',
                          u'gre',
                          name='segmentation_type'),
                  autoincrement=False,
                  nullable=False),
        sa.ForeignKeyConstraint(['cluster_id'],
                                [u'clusters.id'],
                                name=u'neutron_configs_cluster_id_fkey'),
        sa.PrimaryKeyConstraint(u'id',
                                name=u'neutron_configs_pkey')
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

    # NETWORK NAME ENUM DOWNGRADE
    upgrade_enum(
        "network_groups",            # table
        "name",                      # column
        "network_group_name",        # ENUM name
        new_network_group_name,      # old options
        old_network_group_name       # new options
    )

    op.drop_column(
        u'node_nic_interfaces',
        'parent_id'
    )
    op.drop_column(
        'nodes',
        'agent_checksum')
    op.rename_table(
        'net_nic_assignments',
        'net_assignments'
    )

    op.drop_table('net_bond_assignments')
    op.drop_table('node_bond_interfaces')
    drop_enum('bond_mode')
    op.drop_column('nodes', 'agent_checksum')
    op.drop_column('nodes', 'uuid')
    op.drop_table('neutron_config')
    op.drop_table('nova_network_config')
    op.drop_table('networking_configs')
    ### end Alembic commands ###
