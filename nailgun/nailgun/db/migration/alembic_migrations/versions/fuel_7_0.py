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

Revision ID: 39f7c05eec20
Revises: 37608259013
Create Date: 2015-06-23 17:59:16.195289

"""

# revision identifiers, used by Alembic.
from nailgun.db.sqlalchemy.models import fields

revision = '39f7c05eec20'
down_revision = '37608259013'

from alembic import op
import sqlalchemy as sa


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
        'node_nic_interfaces',
        sa.Column('offload_modes',
                  fields.JSON(),
                  nullable=False,
                  server_default='[]'))
    op.add_column(
        'node_bond_interfaces',
        sa.Column('offload_modes',
                  fields.JSON(),
                  nullable=False,
                  server_default='[]'))


def downgrade_schema():
    op.drop_column('node_bond_interfaces', 'offload_modes')
    op.drop_column('node_nic_interfaces', 'offload_modes')


def upgrade_data():
    pass


def downgrade_data():
    pass
