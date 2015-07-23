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

"""Fuel 7.0

Revision ID: 1e50a4903910
Revises: 37608259013
Create Date: 2015-06-24 12:08:04.838393

"""

# revision identifiers, used by Alembic.

revision = '1e50a4903910'
down_revision = '37608259013'

import six
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

from alembic import op
from oslo.serialization import jsonutils

from nailgun.db.sqlalchemy.models import fields
from nailgun.extensions.consts import extensions_migration_buffer_table_name
from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import upgrade_enum
from nailgun.utils.migration import upgrade_release_set_deployable_false


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
    'check_repo_availability',
    'check_repo_availability_with_setup',
    'dump',
    'capacity_log',
    'create_stats_user',
    'remove_stats_user'
)
task_names_new = task_names_old + (
    'spawn_vms',
)


def upgrade():
    op.create_foreign_key(
        'network_groups_nodegroups_fk', 'network_groups', 'nodegroups',
        ['group_id'], ['id'])
    op.create_foreign_key(
        'nodes_nodegroups_fk', 'nodes', 'nodegroups', ['group_id'], ['id'])
    op.alter_column(
        'oswl_stats', 'resource_checksum', existing_type=sa.TEXT(),
        nullable=False)
    op.create_unique_constraint(
        'oswl_stats_cluster_id_created_date_resource_type_unique_key',
        'oswl_stats', ['cluster_id', 'created_date', 'resource_type'])
    op.alter_column('clusters', 'name', type_=sa.TEXT())

    extend_ip_addrs_model_upgrade()
    extend_node_model_upgrade()
    configurable_hostnames_upgrade()
    extend_plugin_model_upgrade()
    upgrade_node_roles_metadata()
    node_roles_as_plugin_upgrade()
    migrate_volumes_into_extension_upgrade()
    networking_templates_upgrade()
    extend_releases_model_upgrade()
    upgrade_task_names()
    vms_conf_upgrade()
    extend_nic_model_upgrade()
    upgrade_cluster_ui_settings()
    upgrade_cluster_bond_settings()
    extensions_field_upgrade()
    set_deployable_false_for_old_releases()
    upgrade_node_labels()
    extend_segmentation_type()
    network_groups_name_upgrade()


def downgrade():
    network_groups_name_downgrade()
    downgrade_node_labels()
    extensions_field_downgrade()
    downgrade_cluster_ui_settings()
    extend_nic_model_downgrade()
    extend_releases_model_downgrade()
    networking_templates_downgrade()
    migrate_volumes_into_extension_downgrade()
    node_roles_as_plugin_downgrade()
    extend_plugin_model_downgrade()
    extend_node_model_downgrade()
    configurable_hostnames_downgrade()
    extend_ip_addrs_model_downgrade()
    downgrade_task_names()
    vms_conf_downgrade()
    extend_segmentation_type_downgrade()

    op.execute('UPDATE clusters SET name=LEFT(name, 50)')
    op.alter_column('clusters', 'name', type_=sa.VARCHAR(50))
    op.drop_constraint(
        'oswl_stats_cluster_id_created_date_resource_type_unique_key',
        'oswl_stats', type_='unique')
    op.alter_column(
        'oswl_stats', 'resource_checksum', existing_type=sa.TEXT(),
        nullable=True)
    op.drop_constraint('nodes_nodegroups_fk', 'nodes', type_='foreignkey')
    op.drop_constraint('network_groups_nodegroups_fk', 'network_groups',
                       type_='foreignkey')


def network_groups_name_upgrade():
    op.alter_column('network_groups',
                    'name',
                    type_=sa.String(length=50),
                    existing_type=sa.Enum(
                        'fuelweb_admin', 'storage',
                        'management', 'public',
                        'fixed', 'private',
                        name='network_group_name'))
    drop_enum('network_group_name')


def network_groups_name_downgrade():
    network_group_name = sa.Enum('fuelweb_admin', 'storage',
                                 'management', 'public',
                                 'fixed', 'private',
                                 name='network_group_name')
    network_group_name.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE network_groups ALTER COLUMN name '
               'TYPE network_group_name '
               'USING name::text::network_group_name')


def extend_node_model_upgrade():
    op.add_column(
        'node_nic_interfaces',
        sa.Column('offloading_modes',
                  fields.JSON(),
                  nullable=False,
                  server_default='[]'))
    op.add_column(
        'node_bond_interfaces',
        sa.Column('offloading_modes',
                  fields.JSON(),
                  nullable=False,
                  server_default='[]'))


def configurable_hostnames_upgrade():
    op.add_column(
        'nodes',
        sa.Column('hostname',
                  sa.String(length=255),
                  nullable=False,
                  server_default='')
    )
    op.create_unique_constraint(
        '_hostname_cluster_uc',
        'nodes',
        [
            'cluster_id',
            'hostname'
        ]
    )

    op.drop_column('nodes', 'fqdn')
    # upgrade data
    connection = op.get_bind()

    update = sa.text(
        """UPDATE nodes SET hostname = 'node-' || id::text""")
    connection.execute(update)


def extend_node_model_downgrade():
    op.drop_column('node_bond_interfaces', 'offloading_modes')
    op.drop_column('node_nic_interfaces', 'offloading_modes')


def configurable_hostnames_downgrade():
    op.drop_constraint('_hostname_cluster_uc', 'nodes',)
    op.drop_column('nodes', 'hostname')
    op.add_column(
        'nodes',
        sa.Column('fqdn',
                  sa.String(length=255),
                  nullable=True)
    )


def extend_ip_addrs_model_upgrade():
    op.alter_column('ip_addrs', 'vip_type',
                    type_=sa.String(length=50),
                    existing_type=sa.Enum('haproxy', 'vrouter',
                    name='network_vip_types'))
    drop_enum('network_vip_types')


def upgrade_task_names():
    upgrade_enum(
        "tasks",                    # table
        "name",                     # column
        "task_name",                # ENUM name
        task_names_old,             # old options
        task_names_new              # new options
    )


def downgrade_task_names():
    upgrade_enum(
        "tasks",                    # table
        "name",                     # column
        "task_name",                # ENUM name
        task_names_new,             # old options
        task_names_old              # new options
    )


def vms_conf_upgrade():
    op.add_column(
        'node_attributes',
        sa.Column(
            'vms_conf',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )


def vms_conf_downgrade():
    op.drop_column('node_attributes', 'vms_conf')


def extend_plugin_model_upgrade():
    op.add_column(
        'plugins',
        sa.Column(
            'network_roles_metadata',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )
    op.add_column(
        'plugins',
        sa.Column(
            'attributes_metadata',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )
    op.add_column(
        'plugins',
        sa.Column(
            'volumes_metadata',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )
    op.add_column(
        'plugins',
        sa.Column(
            'roles_metadata',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )
    op.add_column(
        'plugins',
        sa.Column(
            'deployment_tasks',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )
    op.add_column(
        'plugins',
        sa.Column(
            'tasks',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )


def networking_templates_upgrade():
    op.add_column(
        'networking_configs',
        sa.Column(
            'configuration_template', fields.JSON(),
            nullable=True, server_default=None)
    )
    op.add_column(
        'nodes',
        sa.Column(
            'network_template', fields.JSON(), nullable=True,
            server_default=None)
    )


def networking_templates_downgrade():
    op.drop_column('nodes', 'network_template')
    op.drop_column('networking_configs', 'configuration_template')


def extend_ip_addrs_model_downgrade():
    vrouter_enum = sa.Enum('haproxy', 'vrouter',
                           name='network_vip_types')
    vrouter_enum.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE ip_addrs ALTER COLUMN vip_type '
               'TYPE network_vip_types '
               'USING vip_type::text::network_vip_types')


def extend_releases_model_upgrade():
    op.add_column(
        'releases',
        sa.Column(
            'network_roles_metadata',
            fields.JSON(),
            server_default='[]'))


def extend_plugin_model_downgrade():
    op.drop_column('plugins', 'tasks')
    op.drop_column('plugins', 'deployment_tasks')
    op.drop_column('plugins', 'roles_metadata')
    op.drop_column('plugins', 'volumes_metadata')
    op.drop_column('plugins', 'attributes_metadata')
    op.drop_column('plugins', 'network_roles_metadata')


def extend_segmentation_type():

    segmentation_type_old = ('vlan', 'gre')
    segmentation_type_new = ('vlan', 'gre', 'tun')

    upgrade_enum('neutron_config',
                 'segmentation_type',
                 'segmentation_type',
                 segmentation_type_old,
                 segmentation_type_new)


def extend_segmentation_type_downgrade():

    segmentation_type_old = ('vlan', 'gre')
    segmentation_type_new = ('vlan', 'gre', 'tun')

    upgrade_enum('neutron_config',
                 'segmentation_type',
                 'segmentation_type',
                 segmentation_type_new,
                 segmentation_type_old)


def upgrade_node_roles_metadata():
    connection = op.get_bind()
    select_query = sa.sql.text("SELECT id, roles_metadata FROM releases")
    update_query = sa.sql.text(
        "UPDATE releases SET roles_metadata = :roles_metadata WHERE id = :id")

    for id, roles_metadata in connection.execute(select_query):
        roles_metadata = jsonutils.loads(roles_metadata)
        for role, role_info in six.iteritems(roles_metadata):
            if role in ['controller', 'zabbix-server']:
                role_info['public_ip_required'] = True

        # weight attribute is needed for UI to sort list of
        # default roles
        default_roles_weight = {
            "controller": 10,
            "compute": 20,
            "cinder": 30,
            "cinder-vmware": 40,
            "ceph-osd": 50,
            "mongo": 60,
            "base-os": 70,
            "virt": 80
        }
        for role_name in roles_metadata:
            # if role is not in weight mapping, give it enormous value
            # so it could be put at the end of the role list on UI
            # (unless there is more than 1000 default roles in the system)
            roles_metadata[role_name]['weight'] = \
                default_roles_weight.get(role_name, 10000)

        connection.execute(
            update_query,
            id=id,
            roles_metadata=jsonutils.dumps(roles_metadata))


def migrate_volumes_into_extension_upgrade():
    """Migrate data into intermediate table, from
    which specific extensions will be able to retrieve
    the data. It allows us not to hardcode extension
    tables in core migrations.
    """
    connection = op.get_bind()

    # Create migration buffer table for extensions
    op.create_table(
        extensions_migration_buffer_table_name,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('extension_name', sa.Text(), nullable=False),
        sa.Column('data', fields.JSON()),
        sa.PrimaryKeyConstraint('id'))

    select_query = sa.sql.text("SELECT node_id, volumes FROM node_attributes")
    insert_query = sa.sql.text(
        "INSERT INTO {0} (extension_name, data)"
        "VALUES (:extension_name, :data)".format(
            extensions_migration_buffer_table_name))

    # Fill in the buffer
    for node_id, volumes in connection.execute(select_query):
        connection.execute(
            insert_query,
            data=jsonutils.dumps({
                'node_id': node_id,
                'volumes': jsonutils.loads(volumes)}),
            extension_name='volume_manager')

    # Drop the table after the data were migrated
    op.drop_column('node_attributes', 'volumes')


def migrate_volumes_into_extension_downgrade():
    # NOTE(eli): we don't support data downgrade, so we just change
    # schema to represent previous db schema state
    op.drop_table(extensions_migration_buffer_table_name)
    op.add_column(
        'node_attributes',
        sa.Column('volumes', fields.JSON(), nullable=True))


def node_roles_as_plugin_upgrade():
    op.add_column(
        'nodes',
        sa.Column(
            'roles',
            psql.ARRAY(sa.String(64)),
            server_default='{}',
            nullable=False))
    op.add_column(
        'nodes',
        sa.Column(
            'pending_roles',
            psql.ARRAY(sa.String(64)),
            server_default='{}',
            nullable=False))
    op.add_column(
        'nodes',
        sa.Column(
            'primary_roles',
            psql.ARRAY(sa.String(64)),
            server_default='{}',
            nullable=False))

    connection = op.get_bind()

    # map assoc table to new node columns
    assoc_column_map = {
        'node_roles': 'roles',
        'pending_node_roles': 'pending_roles',
    }

    # select all node-role associations for both roles and pending roles,
    # and gather this information in one dictionary
    node_roles_map = {}
    for assoc_table, column in six.iteritems(assoc_column_map):
        result = connection.execute(sa.text("""
            SELECT nodes.id, roles.name, {assoc_table}.primary
            FROM {assoc_table}
                INNER JOIN roles ON {assoc_table}.role = roles.id
                INNER JOIN nodes ON {assoc_table}.node = nodes.id
            """.format(assoc_table=assoc_table)))

        for nodeid, role, primary in result:
            if nodeid not in node_roles_map:
                node_roles_map[nodeid] = {
                    'roles': [], 'pending_roles': [], 'primary_roles': []}

            if primary:
                node_roles_map[nodeid]['primary_roles'].append(role)

            node_roles_map[nodeid][column].append(role)

    # apply gathered node-role information to new columns
    for nodeid, rolesmap in six.iteritems(node_roles_map):
        connection.execute(
            sa.text("""UPDATE nodes
                       SET roles = :roles,
                           pending_roles = :pending_roles,
                           primary_roles = :primary_roles
                       WHERE id = :id"""),
            id=nodeid,
            roles=rolesmap['roles'],
            pending_roles=rolesmap['pending_roles'],
            primary_roles=rolesmap['primary_roles'],
        )

    # remove legacy tables
    op.drop_table('node_roles')
    op.drop_table('pending_node_roles')
    op.drop_table('roles')


def node_roles_as_plugin_downgrade():
    op.create_table(
        'roles',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column(
            'release_id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column(
            'name', sa.VARCHAR(length=50), autoincrement=False,
            nullable=False),
        sa.ForeignKeyConstraint(
            ['release_id'], [u'releases.id'], name=u'roles_release_id_fkey',
            ondelete=u'CASCADE'),
        sa.PrimaryKeyConstraint('id', name=u'roles_pkey'),
        sa.UniqueConstraint(
            'name', 'release_id', name=u'roles_name_release_id_key'))

    op.create_table(
        'node_roles',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('role', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('node', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('primary', sa.BOOLEAN(), server_default=sa.text(u'false'),
                  autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ['node'], [u'nodes.id'], name=u'node_roles_node_fkey',
            ondelete=u'CASCADE'),
        sa.ForeignKeyConstraint(
            ['role'], [u'roles.id'],
            name=u'node_roles_role_fkey', ondelete=u'CASCADE'),
        sa.PrimaryKeyConstraint('id', name=u'node_roles_pkey'))

    op.create_table(
        'pending_node_roles',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('role', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('node', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            'primary', sa.BOOLEAN(), server_default=sa.text(u'false'),
            autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ['node'], [u'nodes.id'], name=u'pending_node_roles_node_fkey',
            ondelete=u'CASCADE'),
        sa.ForeignKeyConstraint(
            ['role'], [u'roles.id'], name=u'pending_node_roles_role_fkey',
            ondelete=u'CASCADE'),
        sa.PrimaryKeyConstraint('id', name=u'pending_node_roles_pkey'))

    # NOTE(ikalnitsky):
    #
    # WE DO NOT SUPPORT DOWNGRADE DATE MIGRATION BY HISTORICAL REASONS.
    # SO ANY DOWNGRADE WILL LOST DATA.

    op.drop_column('nodes', 'primary_roles')
    op.drop_column('nodes', 'pending_roles')
    op.drop_column('nodes', 'roles')


def extend_releases_model_downgrade():
    op.drop_column('releases', 'network_roles_metadata')


def extend_nic_model_upgrade():
    connection = op.get_bind()
    op.add_column(
        'node_nic_interfaces',
        sa.Column('pxe',
                  sa.Boolean,
                  nullable=False,
                  server_default='false'))
    select_query = sa.sql.text(
        "SELECT ni.id from node_nic_interfaces ni "
        "join net_nic_assignments na on ni.id=na.interface_id "
        "join network_groups ng on ng.id=na.network_id "
        "WHERE ng.name = 'fuelweb_admin'")
    update_query = sa.sql.text(
        "UPDATE node_nic_interfaces SET pxe = true "
        "WHERE id = :id")

    # change 'pxe' property to 'true' value for admin ifaces
    for iface_id in connection.execute(select_query):
        connection.execute(update_query, id=iface_id[0])


def extend_nic_model_downgrade():
    op.drop_column('node_nic_interfaces', 'pxe')


def upgrade_cluster_ui_settings():
    op.add_column(
        'clusters',
        sa.Column(
            'ui_settings',
            fields.JSON(),
            server_default=jsonutils.dumps({
                "view_mode": "standard",
                "filter": {},
                "sort": [{"roles": "asc"}],
                "search": ""
            }),
            nullable=False
        )
    )
    op.drop_column('clusters', 'grouping')


def downgrade_cluster_ui_settings():
    op.add_column(
        'clusters',
        sa.Column(
            'grouping',
            sa.Enum(
                'roles', 'hardware', 'both', name='cluster_grouping'),
            nullable=False,
            default='roles'
        )
    )
    op.drop_column('clusters', 'ui_settings')


def upgrade_cluster_bond_settings():
    connection = op.get_bind()

    select = sa.sql.text(
        "SELECT id, networks_metadata from releases")
    update = sa.sql.text(
        """UPDATE releases
        SET networks_metadata = :networks
        WHERE id = :id""")
    releases = connection.execute(select)
    new_bond_meta = {
        "linux": [
            {
                "values": ["balance-rr", "active-backup", "802.3ad"],
                "condition": "interface:pxe == false"
            },
            {
                "values": ["balance-xor", "broadcast", "balance-tlb",
                           "balance-alb"],
                "condition": "interface:pxe == false and "
                             "'experimental' in version:feature_groups"
            }
        ],
        "ovs": [
            {
                "values": ["active-backup", "balance-slb",
                           "lacp-balance-tcp"],
                "condition": "interface:pxe == false"
            }
        ]
    }

    for release_id, networks_db_meta in releases:
        networks_meta = jsonutils.loads(networks_db_meta)
        db_bond_meta = networks_meta['bonding']['properties']
        for bond_mode in new_bond_meta:
            if bond_mode in db_bond_meta:
                db_bond_meta[bond_mode]['mode'] = new_bond_meta[bond_mode]
        connection.execute(
            update,
            id=release_id,
            networks=jsonutils.dumps(networks_meta)
        )


def extensions_field_upgrade():
    connection = op.get_bind()
    default_extensions = ['volume_manager']

    for table_name in ['nodes', 'releases', 'clusters']:
        op.add_column(
            table_name,
            sa.Column(
                'extensions',
                psql.ARRAY(sa.String(64)),
                server_default='{}',
                nullable=False))

    for table_name in ['releases', 'clusters']:
        select_query = sa.sql.text(
            "SELECT id FROM {0}".format(table_name))
        for record_id in connection.execute(select_query):
            connection.execute(
                sa.text(
                    "UPDATE {0} SET extensions = :extensions "
                    "WHERE id = :id".format(table_name)),
                id=record_id[0],
                extensions=default_extensions)


def extensions_field_downgrade():
    for table_name in ['nodes', 'releases', 'clusters']:
        op.drop_column(table_name, 'extensions')


def set_deployable_false_for_old_releases():
    connection = op.get_bind()
    upgrade_release_set_deployable_false(connection, ['2014.2.2-6.1'])


def upgrade_node_labels():
    op.add_column(
        'nodes',
        sa.Column('labels', fields.JSON(), server_default='{}', nullable=False)
    )


def downgrade_node_labels():
    op.drop_column('nodes', 'labels')
