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

"""Fuel 10.0

Revision ID: c6edea552f1e
Revises: 675105097a69
Create Date: 2016-04-08 15:20:43.989472

"""
from alembic import op
import sqlalchemy as sa

from nailgun.db.sqlalchemy.models import fields

# revision identifiers, used by Alembic.
revision = 'c6edea552f1e'
down_revision = '675105097a69'


def upgrade():
    upgrade_tasks_snapshot()


def downgrade():
    downgrade_tasks_snapshot()


def upgrade_tasks_snapshot():
    op.add_column(
        'tasks',
        sa.Column(
            'tasks_snapshot',
            fields.JSON(),
            nullable=True
        )
    )


def downgrade_tasks_snapshot():
    op.drop_column('tasks', 'tasks_snapshot')
