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

from alembic import op
import sqlalchemy as sa


def upgrade():
    tasks_in_orchestrator_field_upgrade()


def downgrade():
    tasks_in_orchestrator_field_downgrade()


def tasks_in_orchestrator_field_upgrade():
    op.add_column('tasks', sa.Column('in_orchestrator', sa.Boolean,
                                     nullable=False, default=False,
                                     server_default='FALSE', index=True))


def tasks_in_orchestrator_field_downgrade():
    op.drop_column('tasks', 'in_orchestrator')
