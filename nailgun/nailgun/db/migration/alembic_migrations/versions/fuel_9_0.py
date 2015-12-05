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

"""Fuel 9.0

Revision ID: 11a9adc6d36a
Revises: 2f879fa32f00
Create Date: 2015-12-15 17:20:49.519542

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
from oslo_serialization import jsonutils

revision = '11a9adc6d36a'
down_revision = '43b2cb64dae6'


def upgrade():
    upgrade_ip_address()
    update_vips_from_network_roles()


def downgrade():
    downgrade_ip_address()


def upgrade_ip_address():

    op.add_column(
        'ip_addrs',
        sa.Column(
            'is_user_defined',
            sa.Boolean,
            nullable=False,
            default=False,
            server_default="false"
        )
    )

    op.add_column(
        'ip_addrs',
        sa.Column(
            'vip_namespace',
            sa.String(length=25),
            nullable=True,
            default=None,
            server_default=None
        )
    )

    op.alter_column(
        'ip_addrs',
        'vip_type',
        new_column_name='vip_name'
    )


def update_vips_from_network_roles():

    def _update_network_roles_from_db_metadata(query):
        connection = op.get_bind()
        _vip_name_to_vip_data = {}

        select = sa.text(query)
        network_roles_metadata = connection.execute(select)
        for network_roles_json in network_roles_metadata:
            if not network_roles_json or not network_roles_json[0]:
                continue
            network_roles = jsonutils.loads(network_roles_json[0])
            # warning: in current schema it is possible that network
            # role is declared as dict
            if isinstance(network_roles, dict):
                network_roles = [network_roles]
            for network_role in network_roles:
                vips = network_role.get('properties', {}).get('vip', [])
                for vip in vips:
                    _vip_name_to_vip_data[vip['name']] = vip
        return _vip_name_to_vip_data

    roles_vip_name_to_vip_data = {}

    # get namespaces from plugins
    roles_vip_name_to_vip_data.update(
        _update_network_roles_from_db_metadata(
            "SELECT network_roles_metadata from plugins"
        )
    )

    # get namespaces from releases
    roles_vip_name_to_vip_data.update(
        _update_network_roles_from_db_metadata(
            "SELECT network_roles_metadata from releases"
        )
    )

    # perform update
    connection = op.get_bind()
    ip_addrs_select = sa.text(
        "SELECT id, vip_name from ip_addrs"
    )
    ip_addrs = connection.execute(ip_addrs_select)

    ip_addrs_update = sa.sql.text(
        "UPDATE ip_addrs "
        "SET vip_namespace = :vip_namespace WHERE id = :id"
    )

    existing_names_to_id = dict(
        (vip_name, vip_id) for (vip_id, vip_name) in ip_addrs
    )

    for vip_name in existing_names_to_id:

        namespace = roles_vip_name_to_vip_data\
            .get(vip_name, {}).get('namespace')

        # update only if namespace arrived
        if namespace:
            connection.execute(
                ip_addrs_update,
                id=existing_names_to_id[vip_name],
                vip_namespace=namespace
            )


def downgrade_ip_address():
    op.alter_column(
        'ip_addrs',
        'vip_name',
        new_column_name='vip_type',
        type_=sa.String(length=25),
        server_default=None,
        nullable=True
    )

    op.drop_column('ip_addrs', 'is_user_defined')
    op.drop_column('ip_addrs', 'vip_namespace')
