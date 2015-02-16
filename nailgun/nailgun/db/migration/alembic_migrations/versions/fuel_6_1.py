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
import sqlalchemy as sa
from sqlalchemy.sql import text

from nailgun.db.sqlalchemy.models import fields
from nailgun.openstack.common import jsonutils
from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import upgrade_attributes_metadata_6_0_to_6_1
from nailgun.utils.migration import upgrade_enum
from nailgun.utils.migration import upgrade_master_node_settings_6_0_to_6_1
from nailgun.utils.migration import upgrade_role_limits_6_0_to_6_1
from nailgun.utils.migration import upgrade_role_restrictions_6_0_to_6_1


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


def upgrade():
    upgrade_schema()
    upgrade_data()


def downgrade():
    downgrade_data()
    downgrade_schema()


def upgrade_schema():
    op.add_column(
        'clusters',
        sa.Column('deployment_tasks', fields.JSON(), nullable=True))
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
                  default={}))


def downgrade_schema():
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

    op.drop_table('vmware_attributes')
    op.drop_column('releases', 'vmware_attributes_metadata')
    op.drop_column('clusters', 'deployment_tasks')
    op.drop_column('releases', 'deployment_tasks')


def upgrade_data():
    connection = op.get_bind()

    select = text(
        """SELECT id, roles_metadata, attributes_metadata
        from releases""")
    update = text(
        """UPDATE releases
        SET roles_metadata = :roles, attributes_metadata = :attrs
        WHERE id = :id""")
    r = connection.execute(select)

    for release in r:
        roles_meta = upgrade_role_limits_6_0_to_6_1(
            jsonutils.loads(release[1]),
            _limits_to_update)
        roles_meta = upgrade_role_restrictions_6_0_to_6_1(
            roles_meta,
            _new_role_restrictions)
        attributes_meta = upgrade_attributes_metadata_6_0_to_6_1(
            jsonutils.loads(release[2]))
        connection.execute(
            update,
            id=release[0],
            roles=jsonutils.dumps(roles_meta),
            attrs=jsonutils.dumps(attributes_meta)
        )

    upgrade_master_node_settings(connection)


def downgrade_data():
    pass


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
            'condition': (
                "settings:storage.volumes_lvm.value == false and "
                "settings:storage.volumes_vmdk.value == false"),
            'message': "Cinder LVM or VMDK should be enabled in settings"
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
