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
from nailgun.db.sqlalchemy.models import fields
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


def upgrade():
    create_components_table()
    create_release_components_table()
    upgrade_nodegroups_name_cluster_constraint()
    upgrade_release_state()
    task_statuses_upgrade()
    upgrade_cluster_plugins()


def downgrade():
    downgrade_cluster_plugins()
    task_statuses_downgrade()
    downgrade_release_state()
    downgrade_nodegroups_name_cluster_constraint()

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


def downgrade_nodegroups_name_cluster_constraint():
    op.drop_constraint('_name_cluster_uc', 'nodegroups',)


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
            editable.update({p_name: p_attr})
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
