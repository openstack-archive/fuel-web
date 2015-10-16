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

"""empty message

Revision ID: 43b2cb64dae6
Revises: 1e50a4903910
Create Date: 2015-09-03 12:28:11.132934

"""

# revision identifiers, used by Alembic.
revision = '43b2cb64dae6'
down_revision = '1e50a4903910'

import sqlalchemy as sa

from alembic import op

from nailgun.db.sqlalchemy.models.fields import LowercaseString


def upgrade():
    upgrade_all_network_data_from_string_to_appropriate_data_type()


def downgrade():
    downgrade_all_network_data_to_string()


def upgrade_all_network_data_from_string_to_appropriate_data_type():
    string_to_network_type('ip_addrs', 'ip_addr', 'inet')
    string_to_network_type('ip_addr_ranges', 'first', 'inet')
    string_to_network_type('ip_addr_ranges', 'last', 'inet')
    string_to_network_type('network_groups', 'cidr', 'cidr')
    string_to_network_type('network_groups', 'gateway', 'inet')
    string_to_network_type('neutron_config', 'base_mac', 'macaddr')
    string_to_network_type('neutron_config', 'internal_cidr', 'cidr')
    string_to_network_type('neutron_config', 'internal_gateway', 'inet')
    string_to_network_type('nova_network_config', 'fixed_networks_cidr',
                           'cidr')
    string_to_network_type('nodes', 'mac', 'macaddr')
    string_to_network_type('nodes', 'ip', 'inet')
    string_to_network_type('node_nic_interfaces', 'mac', 'macaddr')
    string_to_network_type('node_nic_interfaces', 'ip_addr', 'inet')
    string_to_network_type('node_nic_interfaces', 'netmask', 'inet')
    string_to_network_type('node_bond_interfaces', 'mac', 'macaddr')


def string_to_network_type(table_name, column_name, psql_type):
    op.execute('ALTER TABLE {0} ALTER COLUMN {1}'
               ' TYPE {2} USING cast({1} as {2})'.format(table_name,
                                                         column_name,
                                                         psql_type))


def downgrade_all_network_data_to_string():
    ip_type_to_string('ip_addrs', 'ip_addr', 25)
    ip_type_to_string('ip_addr_ranges', 'first', 25)
    ip_type_to_string('ip_addr_ranges', 'last', 25)
    op.alter_column('network_groups', 'cidr', type_=sa.String(length=25))
    ip_type_to_string('network_groups', 'gateway', 25)
    op.alter_column('neutron_config', 'base_mac', type_=LowercaseString(17))
    op.alter_column('neutron_config', 'internal_cidr',
                    type_=sa.String(length=25))
    ip_type_to_string('neutron_config', 'internal_gateway', 25)
    op.alter_column('nova_network_config', 'fixed_networks_cidr',
                    type_=sa.String(length=25))
    op.alter_column('nodes', 'mac', type_=LowercaseString(17))
    ip_type_to_string('nodes', 'ip', 15)
    op.alter_column('node_nic_interfaces', 'mac', type_=LowercaseString(17))
    ip_type_to_string('node_nic_interfaces', 'ip_addr', 25)
    ip_type_to_string('node_nic_interfaces', 'netmask', 25)
    op.alter_column('node_bond_interfaces', 'mac', type_=sa.String(length=50))


def ip_type_to_string(table_name, column_name, string_len):
    op.execute(
        'ALTER TABLE {0} ALTER COLUMN {1} '
        'TYPE varchar({2}) USING '
        'split_part(cast({1} as varchar({2})), \'/\', 1)'.format(table_name,
                                                                 column_name,
                                                                 string_len)
    )
