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

from nailgun.db.sqlalchemy.models import fields


def upgrade():
    op.create_table('components',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(), nullable=False),
                    sa.Column('hypervisor', fields.JSON(),
                              nullable=False, server_default='[]'),
                    sa.Column('networking', fields.JSON(),
                              nullable=False, server_default='[]'),
                    sa.Column('storage', fields.JSON(),
                              nullable=False, server_default='[]'),
                    sa.Column('additional_services', fields.JSON(),
                              nullable=False, server_default='[]'),
                    sa.Column('plugin_id', sa.Integer(), nullable=True),
                    sa.Column('release_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(
                        ['plugin_id'], ['plugins.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(
                        ['release_id'], ['releases.id'], ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name')
                    )


def downgrade():
    op.drop_table('components')
