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


def upgrade():
    upgrade_nodegroups_constraint()


def downgrade():
    op.drop_constraint('_name_cluster_uc', 'nodegroups',)


def upgrade_nodegroups_constraint():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT name FROM nodegroups GROUP BY name HAVING COUNT(*) >= 2")
    update_query = sa.sql.text(
        "UPDATE nodegroups SET name = :name WHERE id = :ng_id")
    for name in connection.execute(select_query):
        ng_query = sa.sql.text(
            "SELECT id, name FROM nodegroups WHERE name = :name")
        index = 0
        for ng_id, name in connection.execute(ng_query, name=name[0]):
            connection.execute(
                update_query,
                ng_id=ng_id, name="{0}_{1}".format(name, index))
            index += 1

    op.create_unique_constraint(
        '_name_cluster_uc',
        'nodegroups',
        [
            'cluster_id',
            'name'
        ]
    )
