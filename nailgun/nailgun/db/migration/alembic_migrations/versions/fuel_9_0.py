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

"""Fuel 9.0

Revision ID: 11a9adc6d36a
Revises: 2f879fa32f00
Create Date: 2015-12-15 17:20:49.519542

"""

from alembic import op
import six
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.db.sqlalchemy.models import fields
from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import upgrade_enum

revision = '11a9adc6d36a'
down_revision = '43b2cb64dae6'

cluster_statuses_old = (
    'new',
    'deployment',
    'stopped',
    'operational',
    'error',
    'remove',
    'update',
    'update_error'
)
cluster_statuses_new = (
    'new',
    'deployment',
    'stopped',
    'operational',
    'error',
    'remove',
)


def upgrade():
    add_foreign_key_ondelete()
    upgrade_ip_address()
    update_vips_from_network_roles()
    upgrade_node_roles_metadata()
    merge_node_attributes_with_nodes()
    upgrade_node_attributes()
    upgrade_remove_wizard_metadata_from_releases()
    upgrade_deployment_graph()
    drop_legacy_patching()


def downgrade():
    restore_legacy_patching()
    downgrade_deployment_graph()
    downgrade_remove_wizard_metadata_from_releases()
    downgrade_node_attributes()
    downgrade_merge_node_attributes_with_nodes()
    downgrade_node_roles_metadata()
    remove_foreign_key_ondelete()
    downgrade_ip_address()


def remove_foreign_key_ondelete():
    op.drop_constraint(
        'attributes_cluster_id_fkey',
        'attributes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'attributes_cluster_id_fkey',
        'attributes', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'cluster_changes_cluster_id_fkey',
        'cluster_changes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'cluster_changes_cluster_id_fkey',
        'cluster_changes', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'nodegroups_cluster_id_fkey',
        'nodegroups',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodegroups_cluster_id_fkey',
        'nodegroups', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'networking_configs_cluster_id_fkey',
        'networking_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'networking_configs_cluster_id_fkey',
        'networking_configs', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'network_groups_nodegroups_fk',
        'network_groups',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'network_groups_nodegroups_fk',
        'network_groups', 'nodegroups',
        ['group_id'], ['id'],
    )

    op.drop_constraint(
        'neutron_config_id_fkey',
        'neutron_config',
        type_='foreignkey'
    )

    op.create_foreign_key(
        'neutron_config_id_fkey',
        'neutron_config', 'networking_configs',
        ['id'], ['id'],
    )

    op.drop_constraint(
        'nodes_nodegroups_fk',
        'nodes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodes_nodegroups_fk',
        'nodes', 'nodegroups',
        ['group_id'], ['id'],
    )

    op.drop_constraint(
        'nodes_cluster_id_fkey',
        'nodes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodes_cluster_id_fkey',
        'nodes', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'cluster_plugin_links_cluster_id_fkey',
        'cluster_plugin_links',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'cluster_plugin_links_cluster_id_fkey',
        'cluster_plugin_links', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'node_nic_interfaces_parent_id_fkey',
        'node_nic_interfaces',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'node_nic_interfaces_parent_id_fkey',
        'node_nic_interfaces', 'node_bond_interfaces',
        ['parent_id'], ['id'],
    )

    op.drop_constraint(
        'openstack_configs_cluster_id_fkey',
        'openstack_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'openstack_configs_cluster_id_fkey',
        'openstack_configs', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'openstack_configs_node_id_fkey',
        'openstack_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'openstack_configs_node_id_fkey',
        'openstack_configs', 'nodes',
        ['node_id'], ['id'],
    )

    op.drop_constraint(
        'plugin_links_plugin_id_fkey',
        'plugin_links',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'plugin_links_plugin_id_fkey',
        'plugin_links', 'plugins',
        ['plugin_id'], ['id'],
    )

    op.drop_constraint(
        'tasks_cluster_id_fkey',
        'tasks',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'tasks_cluster_id_fkey',
        'tasks', 'clusters',
        ['cluster_id'], ['id'],
    )

    op.drop_constraint(
        'tasks_parent_id_fkey',
        'tasks',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'tasks_parent_id_fkey',
        'tasks', 'tasks',
        ['parent_id'], ['id'],
    )


def add_foreign_key_ondelete():
    op.drop_constraint(
        'attributes_cluster_id_fkey',
        'attributes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'attributes_cluster_id_fkey',
        'attributes', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'cluster_changes_cluster_id_fkey',
        'cluster_changes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'cluster_changes_cluster_id_fkey',
        'cluster_changes', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'nodegroups_cluster_id_fkey',
        'nodegroups',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodegroups_cluster_id_fkey',
        'nodegroups', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'networking_configs_cluster_id_fkey',
        'networking_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'networking_configs_cluster_id_fkey',
        'networking_configs', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'network_groups_nodegroups_fk',
        'network_groups',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'network_groups_nodegroups_fk',
        'network_groups', 'nodegroups',
        ['group_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'network_groups_release_fkey',
        'network_groups',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'network_groups_release_fk',
        'network_groups', 'releases',
        ['release'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'neutron_config_id_fkey',
        'neutron_config',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'neutron_config_id_fkey',
        'neutron_config', 'networking_configs',
        ['id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'nodes_nodegroups_fk',
        'nodes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodes_nodegroups_fk',
        'nodes', 'nodegroups',
        ['group_id'], ['id'],
        ondelete='SET NULL'
    )

    op.drop_constraint(
        'nodes_cluster_id_fkey',
        'nodes',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'nodes_cluster_id_fkey',
        'nodes', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'cluster_plugin_links_cluster_id_fkey',
        'cluster_plugin_links',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'cluster_plugin_links_cluster_id_fkey',
        'cluster_plugin_links', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'node_nic_interfaces_parent_id_fkey',
        'node_nic_interfaces',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'node_nic_interfaces_parent_id_fkey',
        'node_nic_interfaces', 'node_bond_interfaces',
        ['parent_id'], ['id'],
        ondelete='SET NULL'
    )

    op.drop_constraint(
        'openstack_configs_cluster_id_fkey',
        'openstack_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'openstack_configs_cluster_id_fkey',
        'openstack_configs', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'openstack_configs_node_id_fkey',
        'openstack_configs',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'openstack_configs_node_id_fkey',
        'openstack_configs', 'nodes',
        ['node_id'], ['id'],
        ondelete='SET NULL'
    )

    op.drop_constraint(
        'plugin_links_plugin_id_fkey',
        'plugin_links',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'plugin_links_plugin_id_fkey',
        'plugin_links', 'plugins',
        ['plugin_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'tasks_cluster_id_fkey',
        'tasks',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'tasks_cluster_id_fkey',
        'tasks', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )

    op.drop_constraint(
        'tasks_parent_id_fkey',
        'tasks',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'tasks_parent_id_fkey',
        'tasks', 'tasks',
        ['parent_id'], ['id'],
        ondelete='CASCADE'
    )


def upgrade_ip_address():

    op.add_column(
        'ip_addrs',
        sa.Column(
            'is_user_defined',
            sa.Boolean,
            nullable=False,
            default=False,
            server_default="false"
        )
    )

    op.add_column(
        'ip_addrs',
        sa.Column(
            'vip_namespace',
            sa.String(length=25),
            nullable=True,
            default=None,
            server_default=None
        )
    )

    op.alter_column(
        'ip_addrs',
        'vip_type',
        new_column_name='vip_name',
        type_=sa.String(length=25)
    )


def update_vips_from_network_roles():

    def _update_network_roles_from_db_metadata(query):
        connection = op.get_bind()
        _vip_name_to_vip_data = {}

        select = sa.text(query)
        network_roles_metadata = connection.execute(select)
        for network_roles_json in network_roles_metadata:
            if not network_roles_json or not network_roles_json[0]:
                continue
            network_roles = jsonutils.loads(network_roles_json[0])
            # warning: in current schema it is possible that network
            # role is declared as dict
            if isinstance(network_roles, dict):
                network_roles = [network_roles]
            for network_role in network_roles:
                vips = network_role.get('properties', {}).get('vip', [])
                for vip in vips:
                    _vip_name_to_vip_data[vip['name']] = vip
        return _vip_name_to_vip_data

    roles_vip_name_to_vip_data = {}

    # get namespaces from plugins
    roles_vip_name_to_vip_data.update(
        _update_network_roles_from_db_metadata(
            "SELECT network_roles_metadata from plugins"
        )
    )

    # get namespaces from releases
    roles_vip_name_to_vip_data.update(
        _update_network_roles_from_db_metadata(
            "SELECT network_roles_metadata from releases"
        )
    )

    # perform update
    connection = op.get_bind()
    ip_addrs_select = sa.text(
        "SELECT id, vip_name from ip_addrs"
    )
    ip_addrs = connection.execute(ip_addrs_select)

    ip_addrs_update = sa.sql.text(
        "UPDATE ip_addrs "
        "SET vip_namespace = :vip_namespace WHERE id = :id"
    )

    existing_names_to_id = dict(
        (vip_name, vip_id) for (vip_id, vip_name) in ip_addrs
    )

    for vip_name in existing_names_to_id:

        namespace = roles_vip_name_to_vip_data\
            .get(vip_name, {}).get('namespace')

        # update only if namespace arrived
        if namespace:
            connection.execute(
                ip_addrs_update,
                id=existing_names_to_id[vip_name],
                vip_namespace=namespace
            )


def downgrade_ip_address():
    op.alter_column(
        'ip_addrs',
        'vip_name',
        new_column_name='vip_type',
        type_=sa.String(length=25)
    )
    op.drop_column('ip_addrs', 'is_user_defined')
    op.drop_column('ip_addrs', 'vip_namespace')


def upgrade_node_roles_metadata():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, roles_metadata FROM releases "
        "WHERE roles_metadata IS NOT NULL")
    update_query = sa.sql.text(
        "UPDATE releases SET roles_metadata = :roles_metadata WHERE id = :id")

    for id, roles_metadata in connection.execute(select_query):
        roles_metadata = jsonutils.loads(roles_metadata)

        role_groups = {
            'controller': 'base',
            'compute': 'compute',
            'virt': 'compute',
            'compute-vmware': 'compute',
            'ironic': 'compute',
            'cinder': 'storage',
            'cinder-block-device': 'storage',
            'cinder-vmware': 'storage',
            'ceph-osd': 'storage'
        }
        for role_name, role_metadata in six.iteritems(roles_metadata):
            role_metadata['group'] = role_groups\
                .get(role_name, consts.NODE_ROLE_GROUPS.other)

        connection.execute(
            update_query,
            id=id,
            roles_metadata=jsonutils.dumps(roles_metadata),
        )


def downgrade_node_roles_metadata():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, roles_metadata FROM releases "
        "WHERE roles_metadata IS NOT NULL")
    update_query = sa.sql.text(
        "UPDATE releases SET roles_metadata = :roles_metadata WHERE id = :id")

    for id, roles_metadata in connection.execute(select_query):
        roles_metadata = jsonutils.loads(roles_metadata)
        for role_name, role_metadata in six.iteritems(roles_metadata):
            del role_metadata['group']
        connection.execute(
            update_query,
            id=id,
            roles_metadata=jsonutils.dumps(roles_metadata),
        )


def merge_node_attributes_with_nodes():
    connection = op.get_bind()

    op.add_column(
        'nodes',
        sa.Column(
            'vms_conf',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )

    select_query = sa.sql.text('SELECT node_id, vms_conf FROM node_attributes')
    update_query = sa.sql.text(
        'UPDATE nodes SET vms_conf = :vms_conf WHERE id = :node_id')

    for node_id, vms_conf in connection.execute(select_query):
        connection.execute(update_query, node_id=node_id, vms_conf=vms_conf)

    op.drop_table('node_attributes')


def downgrade_merge_node_attributes_with_nodes():
    op.create_table(
        'node_attributes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=True),
        sa.Column('interfaces', fields.JSON(), nullable=True),
        sa.Column('vms_conf', fields.JSON(),
                  nullable=False, server_default='[]'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.drop_column('nodes', 'vms_conf')


def upgrade_node_attributes():
    op.add_column(
        'nodes',
        sa.Column(
            'attributes',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )

    op.add_column(
        'releases',
        sa.Column(
            'node_attributes',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )


def downgrade_node_attributes():
    op.drop_column('releases', 'node_attributes')
    op.drop_column('nodes', 'attributes')


def upgrade_remove_wizard_metadata_from_releases():
    op.drop_column('releases', 'wizard_metadata')


def downgrade_remove_wizard_metadata_from_releases():
    op.add_column(
        'releases',
        sa.Column(
            'wizard_metadata',
            fields.JSON(),
            nullable=True
        )
    )


def drop_legacy_patching():
    upgrade_enum(
        "clusters",                 # table
        "status",                   # column
        "cluster_status",           # ENUM name
        cluster_statuses_old,       # old options
        cluster_statuses_new,       # new options
    )

    op.drop_constraint(
        'fk_pending_release_id',
        'clusters',
        type_='foreignkey'
    )
    op.drop_column('clusters', 'pending_release_id')
    op.drop_column('releases', 'can_update_from_versions')


def restore_legacy_patching():
    op.add_column(
        'releases',
        sa.Column(
            'can_update_from_versions',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        ))
    op.add_column(
        'clusters',
        sa.Column(
            'pending_release_id',
            sa.Integer(),
            nullable=True
        ))
    op.create_foreign_key(
        'fk_pending_release_id',
        'clusters',
        'releases',
        ['pending_release_id'],
        ['id'])

    upgrade_enum(
        "clusters",                 # table
        "status",                   # column
        "cluster_status",           # ENUM name
        cluster_statuses_new,       # new options
        cluster_statuses_old,       # old options
    )


def upgrade_deployment_graph():
    deployment_graph_table = op.create_table(
        'deployment_graphs',

        sa.Column(
            'id',
            sa.INTEGER(),
            nullable=False,
            autoincrement=True,
            primary_key=True),

        sa.Column(
            'verbose_name',
            sa.VARCHAR(length=consts.DEPLOYMENT_GRAPH_NAME_MAX_LEN),
            nullable=True),
    )

    deployment_graph_tasks_table = op.create_table(
        'deployment_graph_tasks',

        sa.Column(
            'id',
            sa.INTEGER(),
            nullable=False,
            autoincrement=True,
            primary_key=True),

        sa.Column(
            'deployment_graph_id',
            sa.INTEGER(),
            autoincrement=False,
            nullable=False),
        sa.ForeignKeyConstraint(
            ['deployment_graph_id'],
            ['deployment_graphs.id'],
            ondelete='CASCADE'),

        sa.Column(
            'task_name',
            sa.VARCHAR(length=consts.DEPLOYMENT_TASK_NAME_MAX_LEN),
            nullable=False),
        sa.UniqueConstraint(
            'deployment_graph_id',
            'task_name',
            name='_task_name_deployment_graph_id_uc'),

        sa.Column(
            'version',
            sa.VARCHAR(consts.DEPLOYMENT_TASK_VERSION_MAX_LEN),
            nullable=False,
            server_default=consts.DEPLOYMENT_TASK_DEFAULT_VERSION,
            default=consts.DEPLOYMENT_TASK_DEFAULT_VERSION),

        sa.Column(
            'condition',
            sa.VARCHAR(consts.DEPLOYMENT_TASK_CONDITION_MAX_LEN),
            nullable=True),

        sa.Column(
            'type',
            sa.Enum(
                *consts.ORCHESTRATOR_TASK_TYPES,
                name='deployment_graph_tasks_type'),
            nullable=False),

        sa.Column(
            'groups',
            psql.ARRAY(sa.String(consts.DEPLOYMENT_TASK_GROUP_NAME_MAX_LEN)),
            default=[],
            nullable=False,
            server_default='{}'),

        sa.Column(
            'tasks',
            psql.ARRAY(sa.String(consts.DEPLOYMENT_TASK_NAME_MAX_LEN)),
            default=[],
            nullable=False,
            server_default='{}'),

        sa.Column(
            'roles',
            psql.ARRAY(sa.String(consts.NODE_ROLE_NAME_MAX_LEN)),
            default=[],
            nullable=False,
            server_default='{}'),

        sa.Column(
            'reexecute_on',
            psql.ARRAY(sa.String(consts.NAILGUN_EVENT_NAME_MAX_LEN)),
            default=[],
            nullable=False,
            server_default='{}'),

        sa.Column(
            'refresh_on',
            psql.ARRAY(sa.String(consts.NAILGUN_EVENT_NAME_MAX_LEN)),
            default=[],
            nullable=False,
            server_default='{}'),

        sa.Column(
            'required_for',
            psql.ARRAY(sa.String(consts.DEPLOYMENT_TASK_NAME_MAX_LEN)),
            default=[],
            nullable=False,
            server_default='{}'),

        sa.Column(
            'requires',
            psql.ARRAY(sa.String(consts.DEPLOYMENT_TASK_NAME_MAX_LEN)),
            default=[],
            nullable=False,
            server_default='{}'),

        sa.Column(
            'cross_depended_by',
            fields.JSON(),
            nullable=False,
            server_default='[]'),

        sa.Column(
            'cross_depends',
            fields.JSON(),
            nullable=False,
            server_default='[]'),


        sa.Column(
            'parameters',
            fields.JSON(),
            default={},
            server_default='{}')
    )

    def create_graph_relation_table(name, fk_field, fk_points_to):
        """Generate m2m relations for deployment graphs."""
        return op.create_table(
            name,
            sa.Column(
                'id',
                sa.INTEGER(),
                nullable=False,
                autoincrement=True,
                primary_key=True),

            sa.Column(
                'type',
                sa.VARCHAR(length=consts.DEPLOYMENT_GRAPH_TYPE_MAX_LEN),
                nullable=False),

            sa.Column(
                'deployment_graph_id',
                sa.INTEGER(),
                nullable=False,
                index=True),
            sa.ForeignKeyConstraint(
                ['deployment_graph_id'],
                ['deployment_graphs.id'],
                ondelete='CASCADE'),

            sa.Column(
                fk_field,
                sa.INTEGER(),
                nullable=False,
                index=True),
            sa.ForeignKeyConstraint(
                [fk_field],
                [fk_points_to],
                ondelete='CASCADE'),

            sa.UniqueConstraint(
                'type',
                fk_field,
                name='type_{0}_uc'.format(fk_field))
        )

    create_graph_relation_table(
        name='release_deployment_graphs',
        fk_field='release_id',
        fk_points_to='releases.id')

    create_graph_relation_table(
        name='plugin_deployment_graphs',
        fk_field='plugin_id',
        fk_points_to='plugins.id')

    create_graph_relation_table(
        name='cluster_deployment_graphs',
        fk_field='cluster_id',
        fk_points_to='clusters.id')

    create_graph_relation_table(
        name='cluster_plugins_deployment_graphs',
        fk_field='cluster_plugin_id',
        fk_points_to='cluster_plugins.id')

    connection = op.get_bind()

    def create_graph_from_json_tasks(json_tasks):
        deployment_graph_id = connection.execute(
            deployment_graph_table.insert(),
            {'verbose_name': consts.DEPLOYMENT_GRAPH_TYPES.default}
        ).inserted_primary_key[0]
        fields_mapping = {
            'id': 'task_name',
            'cross-depends': 'cross_depends',
            'cross-depended-by': 'cross_depended_by',
            'role': 'roles'
        }
        jsonize_fields = ('cross-depends', 'cross-depended-by', 'parameters',)
        for json_task in json_tasks:
            table_task = {}
            for field in json_task:
                value = json_task[field]
                if field in jsonize_fields:
                    value = jsonutils.dumps(value)
                # remap fields
                if field in fields_mapping:
                    # wrap string role to array
                    if field == 'role' and isinstance(value, six.string_types):
                        value = [value]
                    table_task[fields_mapping[field]] = value
                else:
                    table_task[field] = value
            table_task['deployment_graph_id'] = deployment_graph_id
            connection.execute(
                deployment_graph_tasks_table.insert(),
                table_task
            )
        return deployment_graph_id

    for entity_name in ['cluster', 'plugin', 'release']:
        query = sa.text(
            "SELECT id, deployment_tasks "
            "FROM {0}s "
            "WHERE deployment_tasks IS NOT NULL".format(entity_name)
        )
        tasks_by_record = dict(
            (record_id, tasks) for (record_id, tasks)
            in connection.execute(query)
        )
        for entity_id, tasks in six.iteritems(tasks_by_record):

            tasks = jsonutils.loads(tasks)
            if not tasks:
                continue
            deployment_graph_id = create_graph_from_json_tasks(tasks)

            insert_relation_query = sa.text('''
                INSERT INTO {0}_deployment_graphs
                    (deployment_graph_id, {0}_id, type)
                VALUES
                    (:deployment_graph_id, :target_id, :type)
            '''.format(entity_name))

            connection.execute(
                insert_relation_query,
                deployment_graph_id=deployment_graph_id,
                target_id=entity_id,
                type=consts.DEPLOYMENT_GRAPH_TYPES.default
            )

    op.drop_column('plugins', 'deployment_tasks')
    op.drop_column('releases', 'deployment_tasks')
    op.drop_column('clusters', 'deployment_tasks')


def downgrade_deployment_graph():
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
        'releases',
        sa.Column(
            'deployment_tasks',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )
    op.add_column(
        'clusters',
        sa.Column(
            'deployment_tasks',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )
    op.drop_table('cluster_plugins_deployment_graphs')
    op.drop_table('cluster_deployment_graphs')
    op.drop_table('plugin_deployment_graphs')
    op.drop_table('release_deployment_graphs')
    op.drop_table('deployment_graph_tasks')
    drop_enum('deployment_graph_tasks_type')
    op.drop_table('deployment_graphs')
