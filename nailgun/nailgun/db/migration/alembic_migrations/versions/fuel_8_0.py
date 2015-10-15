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
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.utils.migration import drop_enum


def upgrade():
    create_components_table()
    create_release_components_table()
    upgrade_nodegroups_name_cluster_constraint()
    add_baremetal_net_upgrade()


def downgrade():
    op.drop_constraint('_name_cluster_uc', 'nodegroups',)
    op.drop_table('release_components')
    op.drop_table('components')
    drop_enum('component_types')
    add_baremetal_net_downgrade()


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


def add_baremetal_net_upgrade():
    op.add_column('neutron_config',
                  sa.Column('baremetal_gateway', sa.String(length=25),
                            nullable=True))
    op.add_column('neutron_config',
                  sa.Column('baremetal_range', JSON(), nullable=True))


def add_baremetal_net_downgrade():
    op.drop_column('neutron_config', 'baremetal_gateway')
    op.drop_column('neutron_config', 'baremetal_range')
