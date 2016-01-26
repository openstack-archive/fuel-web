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

# revision identifiers, used by Alembic.
revision = '11a9adc6d36a'
down_revision = '43b2cb64dae6'

from alembic import op  # noqa
import sqlalchemy as sa  # noqa

from nailgun import consts


def upgrade():
    upgrade_cluster_add_once_deployed()


def downgrade():
    downgrade_cluster_remove_once_deployed()


def upgrade_cluster_add_once_deployed():
    op.add_column('clusters',
                  sa.Column('once_deployed',
                            sa.Boolean,
                            default=False,
                            server_default='false',
                            nullable=False)
                  )
    update_query = sa.sql.text(
        "UPDATE clusters SET once_deployed = true "
        "WHERE status = :status")
    op.get_bind().execute(update_query,
                          status=consts.CLUSTER_STATUSES.operational)


def downgrade_cluster_remove_once_deployed():
    op.drop_column('clusters', 'once_deployed')
