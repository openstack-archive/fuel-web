#    Copyright 2016 Mirantis, Inc.
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

"""Fuel 9.2

Revision ID: dd6d47652951
Revises: f2314e5d63c9
Create Date: 2016-11-10 17:53:59.348924

"""

# revision identifiers, used by Alembic.
revision = 'dd6d47652951'
down_revision = 'f2314e5d63c9'

from alembic import op
from oslo_serialization import jsonutils
import sqlalchemy as sa


def upgrade():
    upgrade_attributes_metadata()


def downgrade():
    downgrade_attributes_metadata()


def upgrade_attributes_metadata():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, attributes_metadata FROM releases "
        "WHERE attributes_metadata IS NOT NULL")

    update_query = sa.sql.text(
        "UPDATE releases SET attributes_metadata = :attributes_metadata "
        "WHERE id = :id")

    for id, attrs in connection.execute(select_query):
        attrs = jsonutils.loads(attrs)
        attrs['editable']['common']['security_group'] = {
            "value": "iptables_firewall",
            "values": [
                {
                    "data": "ovs_firewall",
                    "label": "Open vSwitch Firewall Driver",
                    "description": "Choose this type of firewall driver if you"
                    " use OVS Brige for networking needs."
                },
                {
                    "data": "iptables_firewall",
                    "label": "Iptables-based Firewall Driver",
                    "description": "Choose this type of firewall driver if you"
                    " use Linux Bridge for networking needs."
                }
            ],
            "group": "security",
            "weight": 20,
            "type": "radio",
        }

        connection.execute(
            update_query,
            id=id,
            attributes_metadata=jsonutils.dumps(attrs))


def downgrade_attributes_metadata():
    connection = op.get_bind()
    select_query = sa.sql.text(
        "SELECT id, attributes_metadata FROM releases "
        "WHERE attributes_metadata IS NOT NULL")

    update_query = sa.sql.text(
        "UPDATE releases SET attributes_metadata = :attributes_metadata "
        "WHERE id = :id")

    for id, attrs in connection.execute(select_query):
        attrs = jsonutils.loads(attrs)
        attrs['editable']['common'].pop('security_group')

        connection.execute(
            update_query,
            id=id,
            attributes_metadata=jsonutils.dumps(attrs))