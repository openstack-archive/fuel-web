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

"""fuel_6_0

Revision ID: 1b1d4016375d
Revises: 52924111f7d8
Create Date: 2014-09-18 12:44:28.327312

"""

# revision identifiers, used by Alembic.
revision = '1b1d4016375d'
down_revision = '52924111f7d8'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.openstack.common import jsonutils
from nailgun.utils.migration import drop_enum
from nailgun.utils.migration import dump_master_node_settings
from nailgun.utils.migration import upgrade_release_attributes_51_to_60
from nailgun.utils.migration import upgrade_release_fill_orchestrator_data
from nailgun.utils.migration import upgrade_release_roles_51_to_60
from nailgun.utils.migration import upgrade_release_set_deployable_false

ENUMS = (
    'action_type',
)


ADDED_ROLES_META = {'controller': {'has_primary': True}}


def upgrade():
    """Upgrade schema and then upgrade data."""
    upgrade_schema()
    upgrade_data()


def downgrade():
    """Downgrade data and then downgrade schema."""
    downgrade_data()
    downgrade_schema()


def upgrade_schema():
    op.add_column(
        'releases',
        sa.Column(
            'is_deployable',
            sa.Boolean(),
            nullable=False,
            server_default='true',
        )
    )
    op.create_table('action_logs',
                    sa.Column('id', sa.Integer, nullable=False),
                    sa.Column(
                        'actor_id',
                        sa.String(length=64),
                        nullable=True
                    ),
                    sa.Column(
                        'action_group',
                        sa.String(length=64),
                        nullable=False
                    ),
                    sa.Column(
                        'action_name',
                        sa.String(length=64),
                        nullable=False
                    ),
                    sa.Column(
                        'action_type',
                        sa.Enum('http_request', 'nailgun_task',
                                name='action_type'),
                        nullable=False
                    ),
                    sa.Column(
                        'start_timestamp',
                        sa.DateTime,
                        nullable=False
                    ),
                    sa.Column(
                        'end_timestamp',
                        sa.DateTime,
                        nullable=True
                    ),
                    sa.Column(
                        'is_sent',
                        sa.Boolean,
                        default=False
                    ),
                    sa.Column(
                        'additional_info',
                        JSON(),
                        nullable=False
                    ),
                    sa.Column(
                        'cluster_id',
                        sa.Integer,
                        nullable=True
                    ),
                    sa.Column(
                        'task_uuid',
                        sa.String(36),
                        nullable=True
                    ),
                    sa.PrimaryKeyConstraint('id'))
    op.create_table('master_node_settings',
                    sa.Column('id', sa.Integer, nullable=False),
                    sa.Column(
                        'master_node_uid',
                        sa.String(36),
                        nullable=False
                    ),
                    sa.Column(
                        'settings',
                        JSON(),
                        default={}
                    ),
                    sa.PrimaryKeyConstraint('id'))
    op.create_table(
        'plugins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('description', sa.String(length=400), nullable=True),
        sa.Column('releases', JSON(), nullable=True),
        sa.Column('fuel_version', JSON(), nullable=True),
        sa.Column('package_version', sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'version', name='_name_version_unique')
    )
    op.create_table(
        'cluster_plugins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plugin_id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ),
        sa.ForeignKeyConstraint(
            ['plugin_id'], ['plugins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'nodegroups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_unique_constraint(None, 'clusters', ['name'])
    op.add_column(
        'network_groups',
        sa.Column('group_id', sa.Integer(), nullable=True)
    )

    op.add_column('nodes', sa.Column('group_id', sa.Integer(), nullable=True))

    # We need this code here because the "upgrade_node_groups" function
    # relies on "cluster_id" column from "network_groups" table.
    connection = op.get_bind()
    upgrade_node_groups(connection)

    op.drop_column('network_groups', 'cluster_id')
    op.add_column(
        'node_roles',
        sa.Column('primary', sa.Boolean(),
                  nullable=False, server_default='false'))
    op.add_column(
        'pending_node_roles',
        sa.Column('primary', sa.Boolean(),
                  nullable=False, server_default='false'))


def upgrade_releases():
    connection = op.get_bind()

    select = text(
        """SELECT id, attributes_metadata, roles_metadata
        from releases""")
    update = text(
        """UPDATE releases
        SET attributes_metadata = :attrs, roles_metadata = :roles
        WHERE id = :id""")
    r = connection.execute(select)

    for release in r:
        attrs_meta = upgrade_release_attributes_51_to_60(
            jsonutils.loads(release[1]))
        roles_meta = upgrade_release_roles_51_to_60(
            jsonutils.loads(release[2]), add_meta=ADDED_ROLES_META)
        connection.execute(
            update,
            id=release[0],
            attrs=jsonutils.dumps(attrs_meta),
            roles=jsonutils.dumps(roles_meta)
        )


def upgrade_data():
    connection = op.get_bind()

    # do not deploy 5.0.x and 5.1.x series
    upgrade_release_set_deployable_false(
        connection, [
            # 5.0.x
            '2014.1',
            '2014.1.1-5.0.1',
            '2014.1.1-5.0.2',
            # 5.1.x
            '2014.1.1-5.1',
            '2014.1.3-5.1.1'])

    # In Fuel 5.x default releases do not have filled orchestrator_data,
    # and defaults one have been used. In Fuel 6.0 we're going to change
    # default paths, so we need to keep them for old releases explicitly.
    #
    # NOTE: all release versions in Fuel 5.x starts with "2014.1"
    upgrade_release_fill_orchestrator_data(connection, ['2014.1%'])

    # generate uid for master node and insert
    # it into master_node_settings table
    dump_master_node_settings(connection)

    upgrade_releases()


def downgrade_schema():
    op.drop_column('releases', 'is_deployable')
    op.drop_table('action_logs')
    op.drop_table('master_node_settings')
    map(drop_enum, ENUMS)
    op.drop_table('cluster_plugins')
    op.drop_table('plugins')
    op.drop_column(u'nodes', 'group_id')
    op.drop_column(u'network_groups', 'group_id')
    op.add_column(
        'network_groups',
        sa.Column('cluster_id', sa.Integer(), sa.ForeignKey('clusters.id'))
    )
    op.drop_column(u'releases', 'wizard_metadata')
    op.drop_table('nodegroups')
    op.drop_column('pending_node_roles', 'primary')
    op.drop_column('node_roles', 'primary')


def upgrade_node_groups(connection):
    cluster_select = sa.text("SELECT id from clusters")
    node_sel = sa.text("SELECT id FROM nodes WHERE cluster_id=:cluster_id")
    node_update = sa.text(
        """UPDATE nodes
        SET group_id=(SELECT id FROM nodegroups WHERE cluster_id=:cluster_id)
        WHERE id=:id""")
    group_insert = sa.text("""INSERT INTO nodegroups (cluster_id, name)
        VALUES(:cluster_id, 'default')""")
    net_select = sa.text("""SELECT id FROM network_groups WHERE
        cluster_id=:cluster_id""")
    net_update = sa.text("""UPDATE network_groups
        SET group_id=(SELECT id FROM nodegroups WHERE cluster_id=:cluster_id)
        WHERE id=:id""")

    clusters = connection.execute(cluster_select)

    for cluster in clusters:
        connection.execute(group_insert, cluster_id=cluster[0])

        # Assign nodes to the newly created node group
        nodes = connection.execute(node_sel, cluster_id=cluster[0])
        for node in nodes:
            connection.execute(node_update, cluster_id=cluster[0], id=node[0])

        # Assign networks to the newly created node group
        nets = connection.execute(net_select, cluster_id=cluster[0])
        for net in nets:
            connection.execute(net_update, cluster_id=cluster[0], id=net[0])


def downgrade_data():
    pass
