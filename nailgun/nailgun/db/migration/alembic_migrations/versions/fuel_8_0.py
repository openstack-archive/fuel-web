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

from nailgun.db.sqlalchemy.models import fields
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

openstack_config_types = (
    'cluster',
    'role',
    'node',
)


def upgrade():
    upgrade_nodegroups_name_cluster_constraint()
    upgrade_release_state()
    task_statuses_upgrade()
    task_names_upgrade()
    add_node_discover_error_upgrade()
    upgrade_neutron_parameters()
    upgrade_cluster_plugins()
    upgrade_add_baremetal_net()
    upgrade_with_components()
    create_openstack_configs_table()


def downgrade():
    downgrade_with_components()
    downgrade_add_baremetal_net()
    downgrade_cluster_plugins()
    downgrade_neutron_parameters()
    add_node_discover_error_downgrade()
    task_names_downgrade()
    task_statuses_downgrade()
    downgrade_release_state()
    downgrade_nodegroups_name_cluster_constraint()
    op.drop_table('openstack_configs')
    drop_enum('openstack_config_types')


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


def downgrade_nodegroups_name_cluster_constraint():
    op.drop_constraint('_name_cluster_uc', 'nodegroups',)


def upgrade_with_components():
    op.add_column(
        'plugins',
        sa.Column(
            'components_metadata',
            fields.JSON(),
            server_default='[]'
        )
    )
    op.add_column(
        'releases',
        sa.Column(
            'components_metadata',
            fields.JSON(),
            server_default='[]'
        )
    )


def create_openstack_configs_table():
    op.create_table(
        'openstack_configs',
        sa.Column('id', sa.Integer, nullable=False),
        sa.Column('is_active', sa.Boolean, nullable=False),
        sa.Column(
            'config_type',
            sa.Enum(*openstack_config_types, name='openstack_config_types'),
            nullable=False),
        sa.Column('cluster_id', sa.Integer, nullable=False),
        sa.Column('node_id', sa.Integer, nullable=True),
        sa.Column('node_role', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('config', fields.JSON, nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id']),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id']),
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


def upgrade_cluster_plugins():
    op.alter_column(
        'cluster_plugins',
        'cluster_id',
        nullable=False
    )
    op.drop_constraint(
        'cluster_plugins_cluster_id_fkey',
        'cluster_plugins',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'cluster_plugins_cluster_id_fkey',
        'cluster_plugins', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )
    op.add_column(
        'cluster_plugins',
        sa.Column(
            'enabled',
            sa.Boolean,
            nullable=False,
            server_default='false'
        )
    )
    op.add_column(
        'cluster_plugins',
        sa.Column(
            'attributes',
            fields.JSON(),
            nullable=False,
            server_default='{}'
        )
    )

    # Iterate over all editable cluster attributes,
    # and set entry in 'cluster_plugins' table

    connection = op.get_bind()

    q_get_plugins = sa.text('''
        SELECT id, name FROM plugins
    ''')
    q_get_cluster_attributes = sa.text('''
        SELECT cluster_id, editable FROM attributes
    ''')
    q_update_cluster_attributes = sa.text('''
        UPDATE attributes
        SET editable = :editable
        WHERE cluster_id = :cluster_id
    ''')
    q_get_cluster_plugins = sa.text('''
        SELECT id FROM cluster_plugins
        WHERE cluster_id = :cluster_id AND plugin_id = :plugin_id
    ''')
    q_update_cluster_plugins = sa.text('''
        UPDATE cluster_plugins
        SET enabled = :enabled, attributes = :attributes
        WHERE cluster_id = :cluster_id AND plugin_id = :plugin_id
    ''')
    q_insert_cluster_plugins = sa.text('''
        INSERT INTO cluster_plugins
            (cluster_id, plugin_id, enabled, attributes)
        VALUES
            (:cluster_id, :plugin_id, :enabled, :attributes)
    ''')

    plugins = list(connection.execute(q_get_plugins))
    for cluster_id, editable in connection.execute(q_get_cluster_attributes):
        editable = jsonutils.loads(editable)
        for plugin_id, plugin_name in plugins:
            if plugin_name in editable:
                attributes = editable.pop(plugin_name)
                metadata = attributes.pop('metadata')

                if connection.execute(q_get_cluster_plugins,
                                      cluster_id=cluster_id,
                                      plugin_id=plugin_id).first():
                    action = q_update_cluster_plugins
                else:
                    action = q_insert_cluster_plugins

                connection.execute(
                    action,
                    cluster_id=cluster_id,
                    plugin_id=plugin_id,
                    enabled=metadata['enabled'],
                    attributes=jsonutils.dumps(attributes)
                )
        connection.execute(
            q_update_cluster_attributes,
            cluster_id=cluster_id,
            editable=jsonutils.dumps(editable)
        )


def downgrade_cluster_plugins():
    connection = op.get_bind()

    q_get_cluster_attributes = sa.text('''
        SELECT clusters.id, attributes.editable
        FROM attributes JOIN clusters ON (attributes.cluster_id = clusters.id)
    ''')
    q_get_plugins = sa.text('''
        SELECT plugins.id, plugins.name, plugins.title,
          cluster_plugins.enabled, cluster_plugins.attributes
        FROM plugins JOIN cluster_plugins
          ON (plugins.id = cluster_plugins.plugin_id)
        WHERE cluster_plugins.cluster_id = :cluster_id
    ''')
    q_update_cluster_attributes = sa.text('''
        UPDATE attributes
        SET editable = :editable
        WHERE cluster_id = :cluster_id
    ''')

    for cluster_id, editable in connection.execute(q_get_cluster_attributes):
        editable = jsonutils.loads(editable)
        plugins = connection.execute(q_get_plugins, cluster_id=cluster_id)
        for p_id, p_name, p_title, p_enabled, p_attr in plugins:
            p_attr = jsonutils.loads(p_attr)
            p_attr['metadata'].update({
                'plugin_id': p_id,
                'enabled': p_enabled,
                'label': p_title
            })
            editable[p_name] = p_attr
            connection.execute(q_update_cluster_attributes,
                               cluster_id=cluster_id,
                               editable=jsonutils.dumps(editable))

    op.drop_column('cluster_plugins', 'attributes')
    op.drop_column('cluster_plugins', 'enabled')
    op.drop_constraint(
        'cluster_plugins_cluster_id_fkey',
        'cluster_plugins',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'cluster_plugins_cluster_id_fkey',
        'cluster_plugins', 'clusters',
        ['cluster_id'], ['id']
    )
    op.alter_column(
        'cluster_plugins',
        'cluster_id',
        nullable=None
    )


def upgrade_add_baremetal_net():
    op.add_column('neutron_config',
                  sa.Column('baremetal_gateway', sa.String(length=25),
                            nullable=True))
    op.add_column('neutron_config',
                  sa.Column('baremetal_range', fields.JSON(), nullable=True,
                            server_default='[]'))


def downgrade_add_baremetal_net():
    op.drop_column('neutron_config', 'baremetal_gateway')
    op.drop_column('neutron_config', 'baremetal_range')


def downgrade_with_components():
    op.drop_column('plugins', 'components_metadata')
    op.drop_column('releases', 'components_metadata')
