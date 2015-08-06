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

Revision ID: 1d5cd969fd05
Revises: 37608259013
Create Date: 2015-08-06 13:12:15.114622

"""

# revision identifiers, used by Alembic.
revision = '1d5cd969fd05'
down_revision = '37608259013'

from alembic import op


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
