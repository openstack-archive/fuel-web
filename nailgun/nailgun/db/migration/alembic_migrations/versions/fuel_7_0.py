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

"""Fuel 7.0 migration

Revision ID: X
Revises: 37608259013
Create Date: 2015-03-16 11:35:19.872214

"""

# revision identifiers, used by Alembic.
revision = 'x'
down_revision = '37608259013'

from alembic import op
import sqlalchemy as sa

from nailgun.db.sqlalchemy.models import fields


def upgrade():
    """Upgrade schema and then upgrade data."""
    upgrade_schema()
    upgrade_data()


def downgrade():
    """Downgrade data and then downgrade schema."""
    downgrade_data()
    downgrade_schema()


def upgrade_data():
    pass


def upgrade_schema():
    op.create_table('virtual_machines_requests',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column(
                        'node_id', sa.Integer(), nullable=False),
                    sa.Column(
                        'created', sa.Boolean(), nullable=False,
                        default=False),
                    sa.Column('cluster_id', sa.Integer(), nullable=False),
                    sa.Column('params', fields.JSON()),
                    sa.PrimaryKeyConstraint('id'),
                    sa.ForeignKeyConstraint(['node_id'], ['nodes.id'],)
                    )


def downgrade_data():
    pass


def downgrade_schema():
    op.drop_table('virtual_machines_requests')
