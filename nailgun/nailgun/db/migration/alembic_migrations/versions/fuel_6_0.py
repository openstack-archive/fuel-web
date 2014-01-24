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

from nailgun.utils.migration import upgrade_release_set_deployable_false


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
        u'network_groups',
        sa.Column('group_id', sa.Integer(), nullable=True)
    )
    op.add_column(u'nodes', sa.Column('group_id', sa.Integer(), nullable=True))


def upgrade_data():
    connection = op.get_bind()

    # do not deploy 5.0.x series
    upgrade_release_set_deployable_false(
        connection, ['2014.1', '2014.1.1-5.0.1', '2014.1.1-5.0.2'])
    upgrade_node_groups(connection)


def downgrade_schema():
    op.drop_column('releases', 'is_deployable')
    op.drop_column(u'nodes', 'group_id')
    op.drop_column(u'network_groups', 'group_id')
    op.drop_column(u'releases', 'wizard_metadata')
    op.drop_table('nodegroups')


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
