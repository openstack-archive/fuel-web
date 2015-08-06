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

"""unique_node_iface_names

Revision ID: 3f42d9f4198f
Revises: 1e50a4903910
Create Date: 2015-08-06 20:28:27.042711

"""

# revision identifiers, used by Alembic.
revision = '3f42d9f4198f'
down_revision = '1e50a4903910'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_unique_constraint('ensure_unique_node_bond_names',
                                'node_bond_interfaces',
                                ['node_id', 'name'],
                                deferrable='True',
                                initially='DEFERRED')
    op.create_unique_constraint('ensure_unique_node_nic_names',
                                'node_nic_interfaces',
                                ['node_id', 'name'],
                                deferrable='True',
                                initially='DEFERRED')


def downgrade():
    op.drop_constraint('ensure_unique_node_nic_names',
                       'node_nic_interfaces',
                       type_='unique')
    op.drop_constraint('ensure_unique_node_bond_names',
                       'node_bond_interfaces',
                       type_='unique')
