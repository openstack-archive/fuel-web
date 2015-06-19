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

"""fuel_7_0

Revision ID: 1a317451edf8
Revises: 37608259013
Create Date: 2015-06-19 10:17:42.604050

"""

# revision identifiers, used by Alembic.
revision = '1a317451edf8'
down_revision = '37608259013'

from alembic import op
import sqlalchemy as sa

from nailgun.db.sqlalchemy.models import fields


connection = op.get_bind()


def upgrade():
    upgrade_schema()
    upgrade_data()


def downgrade():
    downgrade_data()
    downgrade_schema()


def upgrade_schema():
    # plugins table changes
    op.add_column(
        'plugins',
        sa.Column('attributes_metadata', fields.JSON(), nullable=True))
    op.add_column(
        'plugins',
        sa.Column('volumes_metadata', fields.JSON(), nullable=True))
    op.add_column(
        'plugins',
        sa.Column('roles_metadata', fields.JSON(), nullable=True))
    op.add_column(
        'plugins',
        sa.Column('deployment_tasks', fields.JSON(), nullable=True))
    op.add_column(
        'plugins',
        sa.Column('tasks', fields.JSON(), nullable=True))


def downgrade_schema():
    # plugins table changes
    op.drop_column('plugins', 'tasks')
    op.drop_column('plugins', 'deployment_tasks')
    op.drop_column('plugins', 'roles_metadata')
    op.drop_column('plugins', 'volumes_metadata')
    op.drop_column('plugins', 'attributes_metadata')


def upgrade_data():
    pass


def downgrade_data():
    pass
