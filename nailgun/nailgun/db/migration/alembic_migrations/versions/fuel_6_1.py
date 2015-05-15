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

"""Fuel 6.1 migration

Revision ID: 37608259013
Revises: 1b1d4016375d
Create Date: 2014-12-16 11:35:19.872214

"""

# revision identifiers, used by Alembic.
revision = '37608259013'
down_revision = '1b1d4016375d'

from alembic import op
from oslo.serialization import jsonutils
import six
import sqlalchemy as sa
from sqlalchemy.sql import text

from nailgun.db.sqlalchemy.models import fields
from nailgun.utils.migration import downgrade_vip_types_6_1_to_6_0
from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import move_orchestrator_data_to_attributes
from nailgun.utils.migration import \
    upgrade_6_0_to_6_1_plugins_cluster_attrs_use_ids_mapping
from nailgun.utils.migration import upgrade_attributes_metadata_6_0_to_6_1
from nailgun.utils.migration import upgrade_cluster_attributes_6_0_to_6_1
from nailgun.utils.migration import upgrade_enum
from nailgun.utils.migration import upgrade_master_node_settings_6_0_to_6_1
from nailgun.utils.migration import upgrade_network_groups_metadata_6_0_to_6_1
from nailgun.utils.migration import upgrade_networks_metadata_to_6_1
from nailgun.utils.migration import upgrade_release_set_deployable_false
from nailgun.utils.migration import upgrade_role_limits_6_0_to_6_1
from nailgun.utils.migration import upgrade_role_restrictions_6_0_to_6_1
from nailgun.utils.migration import upgrade_ubuntu_cobbler_profile_6_0_to_6_1
from nailgun.utils.migration import upgrade_vip_types_6_0_to_6_1


release_states_old = (
    'not_available',
    'downloading',
    'error',
    'available',
)
release_states_new = (
    'available',
    'unavailable',
)


cluster_changes_old = (
    'networks',
    'attributes',
    'disks',
    'interfaces',
)
cluster_changes_new = (
    'networks',
    'attributes',
    'disks',
    'interfaces',
    'vmware_attributes'
)

bond_modes_old = (
    'active-backup',
    'balance-slb',
    'lacp-balance-tcp',
)

bond_modes_new = (
    # both
    'active-backup',
    # OVS
    'balance-slb',
    'lacp-balance-tcp',
    # linux
    'balance-rr',
    'balance-xor',
    'broadcast',
    '802.3ad',
    'balance-tlb',
    'balance-alb',
)


node_statuses_old = (
    'ready',
    'discover',
    'provisioning',
    'provisioned',
    'deploying',
    'error',
)
node_statuses_new = (
    'ready',
    'discover',
    'provisioning',
    'provisioned',
    'deploying',
    'error',
    'removing',
)


task_names_old = (
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
    'multicast_verification',
    'dump',
    'capacity_log'
)
task_names_new = task_names_old + ('create_stats_user',
                                   'remove_stats_user',
                                   'check_repo_availability',
                                   'check_repo_availability_with_setup')


def upgrade():
    upgrade_schema()
    upgrade_data()


def downgrade():
    downgrade_data()
    downgrade_schema()


def upgrade_schema():
    connection = op.get_bind()

    vrouter_enum = sa.Enum('haproxy', 'vrouter',
                           name='network_vip_types')
    vrouter_enum.create(op.get_bind(), checkfirst=False)

    op.add_column(
        'ip_addrs',
        sa.Column('vip_type', vrouter_enum, nullable=True)
    )

    op.add_column(
        'clusters',
        sa.Column('deployment_tasks', fields.JSON(), nullable=True))
    op.add_column(
        'node_nic_interfaces',
        sa.Column('driver', sa.Text(), nullable=True))
    op.add_column(
        'node_nic_interfaces',
        sa.Column('bus_info', sa.Text(), nullable=True))
    op.add_column(
        'releases',
        sa.Column('deployment_tasks', fields.JSON(), nullable=True))
    op.add_column(
        'releases',
        sa.Column('vmware_attributes_metadata', fields.JSON(), nullable=True))
    op.create_table(
        'vmware_attributes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.Integer()),
        sa.Column('editable', fields.JSON()),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ),
        sa.PrimaryKeyConstraint('id'))

    upgrade_enum(
        'releases',                 # table
        'state',                    # column
        'release_state',            # ENUM name
        release_states_old,         # old options
        release_states_new,         # new options
    )

    upgrade_enum(
        "cluster_changes",          # table
        "name",                     # column
        "possible_changes",         # ENUM name
        cluster_changes_old,        # old options
        cluster_changes_new         # new options
    )

    upgrade_enum(
        "nodes",                    # table
        "status",                   # column
        "node_status",              # ENUM name
        node_statuses_old,          # old options
        node_statuses_new           # new options
    )
    # OpenStack workload statistics
    op.create_table('oswl_stats',
                    sa.Column('id', sa.Integer, nullable=False),
                    sa.Column(
                        'cluster_id',
                        sa.Integer,
                        nullable=False,
                        index=True
                    ),
                    sa.Column(
                        'created_date',
                        sa.Date,
                        nullable=False,
                        index=True
                    ),
                    sa.Column(
                        'updated_time',
                        sa.Time,
                        nullable=False
                    ),
                    sa.Column(
                        'resource_type',
                        sa.Enum('vm',
                                'tenant',
                                'volume',
                                'security_group',
                                'keystone_user',
                                'flavor',
                                'cluster_stats',
                                'image',
                                name='oswl_resource_type'),
                        nullable=False,
                        index=True
                    ),
                    sa.Column(
                        'resource_data',
                        fields.JSON(),
                        nullable=True
                    ),
                    sa.Column(
                        'resource_checksum',
                        sa.Text,
                        nullable=True
                    ),
                    sa.Column(
                        'is_sent',
                        sa.Boolean,
                        nullable=False,
                        default=False,
                        index=True
                    ),
                    sa.PrimaryKeyConstraint('id'))

    op.drop_constraint('node_roles_node_fkey', 'node_roles')
    op.create_foreign_key(
        'node_roles_node_fkey', 'node_roles', 'nodes', ['node'], ['id'],
        ondelete='CASCADE')

    op.drop_constraint('pending_node_roles_node_fkey', 'pending_node_roles')
    op.create_foreign_key(
        'pending_node_roles_node_fkey', 'pending_node_roles', 'nodes',
        ['node'], ['id'], ondelete='CASCADE')

    op.drop_constraint('node_attributes_node_id_fkey', 'node_attributes')
    op.create_foreign_key(
        'node_attributes_node_id_fkey', 'node_attributes', 'nodes',
        ['node_id'], ['id'], ondelete='CASCADE')
    # Introduce linux bonds
    upgrade_enum(
        'node_bond_interfaces',     # table
        'mode',                     # column
        'bond_mode',                # ENUM name
        bond_modes_old,             # old options
        bond_modes_new,             # new options
    )
    # Add bond properties
    op.drop_column('node_bond_interfaces', 'flags')
    op.add_column(
        'node_bond_interfaces',
        sa.Column('bond_properties',
                  fields.JSON(),
                  nullable=False,
                  server_default='{}'))
    # Add interface properties
    op.add_column(
        'node_nic_interfaces',
        sa.Column('interface_properties',
                  fields.JSON(),
                  nullable=False,
                  server_default='{}'))
    op.add_column(
        'node_bond_interfaces',
        sa.Column('interface_properties',
                  fields.JSON(),
                  nullable=False,
                  server_default='{}'))

    move_orchestrator_data_to_attributes(connection)
    op.drop_table('release_orchestrator_data')

    # Plugins migrations
    op.add_column(
        'plugins',
        sa.Column(
            'groups', fields.JSON(), nullable=False, server_default='[]'))
    op.add_column(
        'plugins',
        sa.Column(
            'authors', fields.JSON(), nullable=False, server_default='[]'))
    op.add_column(
        'plugins',
        sa.Column(
            'licenses', fields.JSON(), nullable=False, server_default='[]'))
    op.add_column(
        'plugins',
        sa.Column('homepage', sa.Text(), nullable=True))

    upgrade_enum(
        "tasks",                    # table
        "name",                     # column
        "task_name",                # ENUM name
        task_names_old,             # old options
        task_names_new              # new options
    )


def downgrade_schema():
    upgrade_enum(
        "tasks",                    # table
        "name",                     # column
        "task_name",                # ENUM name
        task_names_new,             # old options
        task_names_old              # new options
    )
    # Add interface properties
    op.drop_column('node_bond_interfaces', 'interface_properties')
    op.drop_column('node_nic_interfaces', 'interface_properties')
    # Add bond properties
    op.drop_column('node_bond_interfaces', 'bond_properties')
    op.add_column(
        'node_bond_interfaces',
        sa.Column('flags', fields.JSON(), nullable=True))
    # Introduce linux bonds
    upgrade_enum(
        'node_bond_interfaces',     # table
        'mode',                     # column
        'bond_mode',                # ENUM name
        bond_modes_new,             # new options
        bond_modes_old,             # old options
    )
    # OpenStack workload statistics
    op.drop_table('oswl_stats')
    drop_enum('oswl_resource_type')

    upgrade_enum(
        "cluster_changes",          # table
        "name",                     # column
        "possible_changes",         # ENUM name
        cluster_changes_new,        # new options
        cluster_changes_old,        # old options
    )

    upgrade_enum(
        'releases',                 # table
        'state',                    # column
        'release_state',            # ENUM name
        release_states_new,         # new options
        release_states_old,         # old options
    )

    upgrade_enum(
        "nodes",                    # table
        "status",                   # column
        "node_status",              # ENUM name
        node_statuses_new,          # old options
        node_statuses_old           # new options
    )

    op.create_table(
        'release_orchestrator_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('release_id', sa.Integer(), nullable=False),
        sa.Column('repo_metadata', fields.JSON(), nullable=False),
        sa.Column(
            'puppet_manifests_source', sa.Text(), nullable=False),
        sa.Column(
            'puppet_modules_source', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ),
        sa.PrimaryKeyConstraint('id'))

    op.drop_table('vmware_attributes')
    op.drop_column('releases', 'vmware_attributes_metadata')
    op.drop_column('clusters', 'deployment_tasks')
    op.drop_column('node_nic_interfaces', 'driver')
    op.drop_column('node_nic_interfaces', 'bus_info')
    op.drop_column('releases', 'deployment_tasks')
    op.drop_constraint('node_roles_node_fkey', 'node_roles')
    op.create_foreign_key(
        'node_roles_node_fkey', 'node_roles', 'nodes', ['node'], ['id'])

    op.drop_constraint('pending_node_roles_node_fkey', 'pending_node_roles')
    op.create_foreign_key(
        'pending_node_roles_node_fkey', 'pending_node_roles', 'nodes',
        ['node'], ['id'])

    op.drop_constraint('node_attributes_node_id_fkey', 'node_attributes')
    op.create_foreign_key(
        'node_attributes_node_id_fkey', 'node_attributes', 'nodes',
        ['node_id'], ['id'])
    op.drop_column('ip_addrs', 'vip_type')
    drop_enum('network_vip_types')

    # Plugins table changes
    op.drop_column('plugins', 'groups')
    op.drop_column('plugins', 'authors')
    op.drop_column('plugins', 'licenses')
    op.drop_column('plugins', 'homepage')


def upgrade_data():
    connection = op.get_bind()

    select = text(
        """SELECT id, roles_metadata, attributes_metadata, networks_metadata
        from releases""")
    update = text(
        """UPDATE releases
        SET roles_metadata = :roles, attributes_metadata = :attrs,
        networks_metadata = :networks
        WHERE id = :id""")
    r = connection.execute(select)

    for release in r:
        roles_meta = upgrade_role_limits_6_0_to_6_1(
            jsonutils.loads(release[1]),
            _limits_to_update)
        roles_meta = upgrade_role_restrictions_6_0_to_6_1(
            roles_meta,
            _new_role_restrictions)
        for role_name, role in six.iteritems(roles_meta):
            role.update(_new_roles_metadata.get(role_name, {}))
        attributes_meta = upgrade_attributes_metadata_6_0_to_6_1(
            jsonutils.loads(release[2]))
        networks_meta = upgrade_networks_metadata_to_6_1(
            jsonutils.loads(release[3]), _bonding_metadata)
        connection.execute(
            update,
            id=release[0],
            roles=jsonutils.dumps(roles_meta),
            attrs=jsonutils.dumps(attributes_meta),
            networks=jsonutils.dumps(networks_meta),
        )

    upgrade_master_node_settings(connection)
    upgrade_6_0_to_6_1_plugins_cluster_attrs_use_ids_mapping(connection)
    upgrade_ubuntu_cobbler_profile_6_0_to_6_1(connection)
    upgrade_cluster_attributes_6_0_to_6_1(connection)
    upgrade_vip_types_6_0_to_6_1(connection)
    upgrade_network_groups_metadata_6_0_to_6_1(connection)

    # do not deploy 6.0.x releases
    upgrade_release_set_deployable_false(
        connection, [
            '2014.2-6.0',
            '2014.2.2-6.0.1'])


def downgrade_data():
    connection = op.get_bind()
    delete = text(
        """DELETE FROM cluster_changes
        WHERE name = 'vmware_attributes'""")
    connection.execute(delete)

    downgrade_vip_types_6_1_to_6_0(connection)


def upgrade_master_node_settings(connection):
    select = text(
        "SELECT master_node_uid, settings FROM master_node_settings"
    )
    update = text(
        """UPDATE master_node_settings
        SET settings = :settings
        WHERE master_node_uid = :uid""")

    masters = connection.execute(select)

    for master in masters:
        settings = upgrade_master_node_settings_6_0_to_6_1(
            jsonutils.loads(master[1]))

        connection.execute(
            update,
            uid=master[0],
            settings=jsonutils.dumps(settings))


_limits_to_update = {
    'controller': {
        'min': 1,
        'overrides': [
            {
                'condition': "cluster:mode == 'multinode'",
                'max': 1,
                'message': (
                    "Multi-node environment can not have more than "
                    "one controller node.")
            },
            {
                'condition': "cluster:mode == 'ha_compact'",
                'recommended': 3,
                'message': (
                    "At least 3 controller nodes are recommended for "
                    "HA deployment.")
            }
        ]
    },
    'compute': {
        'recommended': 1
    },
    'cinder': {
        'overrides': [
            {
                'condition': "settings:storage.volumes_lvm.value == true",
                'recommended': 1,
                'message': (
                    "At least 1 Cinder node is recommended when "
                    "Cinder LVM is selected")
            }
        ]
    },
    'ceph-osd': {
        'overrides': [
            {
                'condition': "settings:storage.volumes_ceph.value == true",
                'min': "settings:storage.osd_pool_size.value"
            },
            {
                'condition': "settings:storage.images_ceph.value == true",
                'min': 1
            }
        ]
    },
    'mongo': {
        'min': 1,
        'overrides': [
            {
                'condition': "cluster:mode != 'ha_compact'",
                'max': 1,
                'message': (
                    "At most 1 MongoDB node can be added for non-HA "
                    "deployment")
            },
            {
                'condition': "cluster:mode == 'ha_compact'",
                'recommended': 3,
                'message': (
                    "At least 3 MongoDB nodes are recommended for HA "
                    "deployment.")
            }
        ]
    },
    'zabbix-server': {
        'max': 1
    }
}


_new_role_restrictions = {
    'compute': [
        {
            'condition': "settings:common.libvirt_type.value == 'vcenter'",
            'message': (
                "Computes cannot be added to environment with "
                "vCenter hypervisor")
        }
    ],
    'cinder': [
        {
            'condition': "settings:storage.volumes_lvm.value == false",
            'message': "Cinder LVM should be enabled in settings"
        },
        # NOTE: https://bugs.launchpad.net/fuel/+bug/1372914 - Prohibit
        #  possibility of adding cinder nodes to an environment with Ceph RBD
        {
            'condition': "settings:storage.volumes_ceph.value == true",
            'message': "Ceph RBD cannot be used with Cinder"
        }
    ],
    'ceph-osd': [
        {
            'condition': (
                "settings:common.libvirt_type.value == 'vcenter' "
                "and settings:storage.images_ceph.value == false"),
            'message': "Ceph RBD for images should be enabled in settings."
        },
        # NOTE: we want a disjoint condition from the one with vCenter so user
        #  will not get 2 messages at once in case when vCenter is selected
        #  and images_ceph.value is false
        {
            'condition': (
                "settings:common.libvirt_type.value != 'vcenter' "
                "and settings:storage.volumes_ceph.value == false "
                "and settings:storage.images_ceph.value == false"),
            'message': "Ceph must be enabled in settings"
        }
    ]
}


_new_roles_metadata = {
    "mongo": {
        "has_primary": True,
    }
}


_bonding_metadata = {
    "availability": [
        {"ovs": "'experimental' in version:feature_groups and "
                "cluster:net_provider != 'neutron' and "
                "settings:storage.iser.value == false and "
                "settings:neutron_mellanox.plugin.value != 'ethernet'"},
        {"linux": "false"}
    ],
    "properties": {
        "ovs": {
            "mode": [
                {
                    "values": ["active-backup", "balance-slb",
                               "lacp-balance-tcp"]
                }
            ]
        }
    }
}
