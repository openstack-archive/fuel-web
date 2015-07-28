# -*- coding: utf-8 -*-

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

"""a

Revision ID: 3b5d115d7e49
Revises: None
Create Date: 2015-07-17 19:46:59.579553

"""

# revision identifiers, used by Alembic.
revision = '3b5d115d7e49'
down_revision = None


from alembic import context
from alembic import op

import sqlalchemy as sa

table_prefix = context.config.get_main_option('table_prefix')
table_upgrade_relation_name = '{0}relations'.format(table_prefix)


def upgrade():
    op.create_table(
        table_upgrade_relation_name,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('orig_cluster_id', sa.Integer(), nullable=False),
        sa.Column('seed_cluster_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('orig_cluster_id'),
        sa.UniqueConstraint('seed_cluster_id'))


def downgrade():
    op.drop_table(table_upgrade_relation_name)
