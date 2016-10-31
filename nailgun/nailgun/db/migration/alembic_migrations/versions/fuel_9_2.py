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

"""fuel_9_2

Revision ID: f53b7d018380
Revises: f2314e5d63c9
Create Date: 2016-10-31 14:17:15.506768

"""

# revision identifiers, used by Alembic.
revision = 'f53b7d018380'
down_revision = 'f2314e5d63c9'

from alembic import op
import sqlalchemy as sa


def upgrade():
    disable_ubuntu_uca()

def downgrade():
    enable_ubuntu_uca()

def _execute_wo_binds (sqltext):
    connection = op.get_bind()
    connection.execute(sqltext)

def disable_ubuntu_uca():
    _execute_wo_binds(sa.sql.text(
        "UPDATE releases SET state='manageonly' WHERE name='Mitaka on Ubuntu+UCA 14.04'"
    ))

def enable_ubuntu_uca():
    _execute_wo_binds(sa.sql.text(
        "UPDATE releases SET state='available' WHERE name='Mitaka on Ubuntu+UCA 14.04'"
    ))
