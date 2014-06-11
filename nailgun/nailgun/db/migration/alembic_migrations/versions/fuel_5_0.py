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

"""fuel_5_0

Revision ID: 1a1504d469f8
Revises: None
Create Date: 2014-04-30 16:16:44.513714

"""

# revision identifiers, used by Alembic.
revision = '1a1504d469f8'
down_revision = None

from alembic import op
import sqlalchemy as sa

from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.fields import LowercaseString
from nailgun.utils.migration import drop_enum

ENUMS = (
    'bond_mode',
    'cluster_grouping',
    'cluster_mode',
    'cluster_net_manager',
    'cluster_status',
    'license_type',
    'net_l23_provider',
    'net_provider',
    'network_group_name',
    'node_error_type',
    'node_status',
    'notif_topic',
    'notif_status',
    'possible_changes',
    'release_state',
    'segmentation_type',
    'task_name',
    'task_status')


def upgrade():
    op.create_table('red_hat_accounts',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column(
                        'username', sa.String(length=100), nullable=False),
                    sa.Column(
                        'password', sa.String(length=100), nullable=False),
                    sa.Column('license_type', sa.Enum(
                        'rhsm', 'rhn', name='license_type'), nullable=False),
                    sa.Column(
                        'satellite', sa.String(length=250), nullable=True),
                    sa.Column(
                        'activation_key', sa.String(length=300),
                        nullable=True),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('capacity_log',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('report', JSON(), nullable=True),
                    sa.Column('datetime', sa.DateTime(), nullable=True),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('releases',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.Unicode(length=100), nullable=False),
                    sa.Column('version', sa.String(length=30), nullable=False),
                    sa.Column('description', sa.Unicode(), nullable=True),
                    sa.Column(
                        'operating_system', sa.String(length=50),
                        nullable=False),
                    sa.Column('state', sa.Enum('not_available', 'downloading',
                                               'error', 'available',
                                               name='release_state'),
                              nullable=False),
                    sa.Column('networks_metadata', JSON(), nullable=True),
                    sa.Column('attributes_metadata', JSON(), nullable=True),
                    sa.Column('volumes_metadata', JSON(), nullable=True),
                    sa.Column('modes_metadata', JSON(), nullable=True),
                    sa.Column('roles_metadata', JSON(), nullable=True),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name', 'version')
                    )
    op.create_table('clusters',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('mode', sa.Enum(
                        'multinode', 'ha_full', 'ha_compact',
                        name='cluster_mode'), nullable=False),
                    sa.Column('status', sa.Enum('new', 'deployment', 'stopped',
                                                'operational', 'error',
                                                'remove',
                                                name='cluster_status'),
                              nullable=False),
                    sa.Column('net_provider', sa.Enum(
                        'nova_network', 'neutron', name='net_provider'),
                        nullable=False),
                    sa.Column('grouping', sa.Enum(
                        'roles', 'hardware', 'both', name='cluster_grouping'),
                        nullable=False),
                    sa.Column('name', sa.Unicode(length=50), nullable=False),
                    sa.Column('release_id', sa.Integer(), nullable=False),
                    sa.Column(
                        'replaced_deployment_info', JSON(), nullable=True),
                    sa.Column(
                        'replaced_provisioning_info', JSON(),
                        nullable=True),
                    sa.Column('is_customized', sa.Boolean(), nullable=True),
                    sa.Column(
                        'fuel_version', sa.Text, nullable=False),
                    sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name')
                    )
    op.create_table('release_orchestrator_data',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('release_id', sa.Integer(), nullable=False),
                    sa.Column('repo_metadata', JSON(), nullable=False),
                    sa.Column(
                        'puppet_manifests_source', sa.Text(), nullable=False),
                    sa.Column(
                        'puppet_modules_source', sa.Text(), nullable=False),
                    sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('roles',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('release_id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=50), nullable=False),
                    sa.ForeignKeyConstraint(
                        ['release_id'], ['releases.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name', 'release_id')
                    )
    op.create_table('nodes',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('uuid', sa.String(length=36), nullable=False),
                    sa.Column('cluster_id', sa.Integer(), nullable=True),
                    sa.Column('name', sa.Unicode(length=100), nullable=True),
                    sa.Column('status', sa.Enum('ready', 'discover',
                                                'provisioning', 'provisioned',
                                                'deploying', 'error',
                                                name='node_status'),
                              nullable=False),
                    sa.Column('meta', JSON(), nullable=True),
                    sa.Column('mac', LowercaseString(), nullable=False),
                    sa.Column('ip', sa.String(length=15), nullable=True),
                    sa.Column('fqdn', sa.String(length=255), nullable=True),
                    sa.Column(
                        'manufacturer', sa.Unicode(length=50), nullable=True),
                    sa.Column(
                        'platform_name', sa.String(length=150), nullable=True),
                    sa.Column('kernel_params', sa.Text(), nullable=True),
                    sa.Column('progress', sa.Integer(), nullable=True),
                    sa.Column(
                        'os_platform', sa.String(length=150), nullable=True),
                    sa.Column('pending_addition', sa.Boolean(), nullable=True),
                    sa.Column('pending_deletion', sa.Boolean(), nullable=True),
                    sa.Column('error_type', sa.Enum(
                        'deploy', 'provision', 'deletion',
                        name='node_error_type'), nullable=True),
                    sa.Column(
                        'error_msg', sa.String(length=255), nullable=True),
                    sa.Column('timestamp', sa.DateTime(), nullable=False),
                    sa.Column('online', sa.Boolean(), nullable=True),
                    sa.Column(
                        'agent_checksum', sa.String(length=40), nullable=True),
                    sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('mac'),
                    sa.UniqueConstraint('uuid')
                    )
    op.create_table('tasks',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('cluster_id', sa.Integer(), nullable=True),
                    sa.Column('uuid', sa.String(length=36), nullable=False),
                    sa.Column('name', sa.Enum('super', 'deploy', 'deployment',
                                              'provision', 'stop_deployment',
                                              'reset_environment',
                                              'node_deletion',
                                              'cluster_deletion',
                                              'check_before_deployment',
                                              'check_networks',
                                              'verify_networks', 'check_dhcp',
                                              'verify_network_connectivity',
                                              'redhat_setup',
                                              'redhat_check_credentials',
                                              'redhat_check_licenses',
                                              'redhat_download_release',
                                              'redhat_update_cobbler_profile',
                                              'dump', 'capacity_log',
                                              name='task_name'),
                              nullable=False),
                    sa.Column('message', sa.Text(), nullable=True),
                    sa.Column('status', sa.Enum(
                        'ready', 'running', 'error', name='task_status'),
                        nullable=False),
                    sa.Column('progress', sa.Integer(), nullable=True),
                    sa.Column('cache', JSON(), nullable=True),
                    sa.Column('result', JSON(), nullable=True),
                    sa.Column('parent_id', sa.Integer(), nullable=True),
                    sa.Column('weight', sa.Float(), nullable=True),
                    sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ),
                    sa.ForeignKeyConstraint(['parent_id'], ['tasks.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('networking_configs',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column(
                        'discriminator', sa.String(length=50), nullable=True),
                    sa.Column('cluster_id', sa.Integer(), nullable=True),
                    sa.Column('dns_nameservers', JSON(), nullable=True),
                    sa.Column('floating_ranges', JSON(), nullable=True),
                    sa.ForeignKeyConstraint(
                        ['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('network_groups',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.Enum('fuelweb_admin', 'storage',
                                              'management',
                                              'public', 'fixed', 'private',
                                              name='network_group_name'),
                              nullable=False),
                    sa.Column('release', sa.Integer(), nullable=True),
                    sa.Column('cluster_id', sa.Integer(), nullable=True),
                    sa.Column('vlan_start', sa.Integer(), nullable=True),
                    sa.Column('cidr', sa.String(length=25), nullable=True),
                    sa.Column('gateway', sa.String(length=25), nullable=True),
                    sa.Column('meta', JSON(), nullable=True),
                    sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ),
                    sa.ForeignKeyConstraint(['release'], ['releases.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('attributes',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('cluster_id', sa.Integer(), nullable=True),
                    sa.Column('editable', JSON(), nullable=True),
                    sa.Column('generated', JSON(), nullable=True),
                    sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('nova_network_config',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column(
                        'fixed_networks_cidr', sa.String(length=25),
                        nullable=True),
                    sa.Column(
                        'fixed_networks_vlan_start', sa.Integer(),
                        nullable=True),
                    sa.Column(
                        'fixed_network_size', sa.Integer(), nullable=False),
                    sa.Column(
                        'fixed_networks_amount', sa.Integer(), nullable=False),
                    sa.Column('net_manager', sa.Enum(
                        'FlatDHCPManager', 'VlanManager',
                        name='cluster_net_manager'), nullable=False),
                    sa.ForeignKeyConstraint(
                        ['id'], ['networking_configs.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('node_roles',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('role', sa.Integer(), nullable=True),
                    sa.Column('node', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['node'], ['nodes.id'], ),
                    sa.ForeignKeyConstraint(
                        ['role'], ['roles.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('cluster_changes',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('cluster_id', sa.Integer(), nullable=True),
                    sa.Column('node_id', sa.Integer(), nullable=True),
                    sa.Column('name', sa.Enum(
                        'networks', 'attributes', 'disks',
                        name='possible_changes'), nullable=False),
                    sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ),
                    sa.ForeignKeyConstraint(
                        ['node_id'], ['nodes.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('node_attributes',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('node_id', sa.Integer(), nullable=True),
                    sa.Column('volumes', JSON(), nullable=True),
                    sa.Column('interfaces', JSON(), nullable=True),
                    sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('notifications',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('cluster_id', sa.Integer(), nullable=True),
                    sa.Column('node_id', sa.Integer(), nullable=True),
                    sa.Column('task_id', sa.Integer(), nullable=True),
                    sa.Column('topic', sa.Enum(
                        'discover', 'done', 'error', 'warning',
                        name='notif_topic'), nullable=False),
                    sa.Column('message', sa.Text(), nullable=True),
                    sa.Column(
                        'status', sa.Enum('read', 'unread',
                                          name='notif_status'),
                        nullable=False),
                    sa.Column('datetime', sa.DateTime(), nullable=False),
                    sa.ForeignKeyConstraint(
                        ['cluster_id'], ['clusters.id'], ondelete='SET NULL'),
                    sa.ForeignKeyConstraint(
                        ['node_id'], ['nodes.id'], ondelete='SET NULL'),
                    sa.ForeignKeyConstraint(
                        ['task_id'], ['tasks.id'], ondelete='SET NULL'),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('node_bond_interfaces',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('node_id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=32), nullable=False),
                    sa.Column('mac', LowercaseString(), nullable=True),
                    sa.Column('state', sa.String(length=25), nullable=True),
                    sa.Column('flags', JSON(), nullable=True),
                    sa.Column('mode', sa.Enum('active-backup', 'balance-slb',
                                              'lacp-balance-tcp',
                                              name='bond_mode'),
                              nullable=False),
                    sa.ForeignKeyConstraint(
                        ['node_id'], ['nodes.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('ip_addrs',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('network', sa.Integer(), nullable=True),
                    sa.Column('node', sa.Integer(), nullable=True),
                    sa.Column('ip_addr', sa.String(length=25), nullable=False),
                    sa.ForeignKeyConstraint(
                        ['network'], ['network_groups.id'],
                        ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(
                        ['node'], ['nodes.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('ip_addr_ranges',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('network_group_id', sa.Integer(), nullable=True),
                    sa.Column('first', sa.String(length=25), nullable=False),
                    sa.Column('last', sa.String(length=25), nullable=False),
                    sa.ForeignKeyConstraint(
                        ['network_group_id'], ['network_groups.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('neutron_config',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('vlan_range', JSON(), nullable=True),
                    sa.Column('gre_id_range', JSON(), nullable=True),
                    sa.Column(
                        'base_mac', LowercaseString(), nullable=False),
                    sa.Column(
                        'internal_cidr', sa.String(length=25), nullable=True),
                    sa.Column(
                        'internal_gateway', sa.String(length=25),
                        nullable=True),
                    sa.Column('segmentation_type', sa.Enum(
                        'vlan', 'gre', name='segmentation_type'),
                        nullable=False),
                    sa.Column('net_l23_provider', sa.Enum(
                        'ovs', name='net_l23_provider'), nullable=False),
                    sa.ForeignKeyConstraint(
                        ['id'], ['networking_configs.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('pending_node_roles',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('role', sa.Integer(), nullable=True),
                    sa.Column('node', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['node'], ['nodes.id'], ),
                    sa.ForeignKeyConstraint(
                        ['role'], ['roles.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('node_nic_interfaces',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('node_id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=128), nullable=False),
                    sa.Column('mac', LowercaseString(), nullable=False),
                    sa.Column('max_speed', sa.Integer(), nullable=True),
                    sa.Column('current_speed', sa.Integer(), nullable=True),
                    sa.Column('ip_addr', sa.String(length=25), nullable=True),
                    sa.Column('netmask', sa.String(length=25), nullable=True),
                    sa.Column('state', sa.String(length=25), nullable=True),
                    sa.Column('parent_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(
                        ['node_id'], ['nodes.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(
                        ['parent_id'], ['node_bond_interfaces.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('net_bond_assignments',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('network_id', sa.Integer(), nullable=False),
                    sa.Column('bond_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(
                        ['bond_id'], ['node_bond_interfaces.id'],
                        ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(
                        ['network_id'], ['network_groups.id'],
                        ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('net_nic_assignments',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('network_id', sa.Integer(), nullable=False),
                    sa.Column('interface_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(
                        ['interface_id'], ['node_nic_interfaces.id'],
                        ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(
                        ['network_id'], ['network_groups.id'],
                        ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id')
                    )


def downgrade():
    op.drop_table('net_nic_assignments')
    op.drop_table('net_bond_assignments')
    op.drop_table('node_nic_interfaces')
    op.drop_table('pending_node_roles')
    op.drop_table('neutron_config')
    op.drop_table('ip_addr_ranges')
    op.drop_table('ip_addrs')
    op.drop_table('node_bond_interfaces')
    op.drop_table('notifications')
    op.drop_table('node_attributes')
    op.drop_table('cluster_changes')
    op.drop_table('node_roles')
    op.drop_table('nova_network_config')
    op.drop_table('attributes')
    op.drop_table('network_groups')
    op.drop_table('networking_configs')
    op.drop_table('tasks')
    op.drop_table('nodes')
    op.drop_table('roles')
    op.drop_table('release_orchestrator_data')
    op.drop_table('clusters')
    op.drop_table('releases')
    op.drop_table('capacity_log')
    op.drop_table('red_hat_accounts')
    map(drop_enum, ENUMS)
