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

"""volume_manager

Revision ID: 086cde3de7cf
Revises: None
Create Date: 2015-06-19 16:16:44.513714

"""

# revision identifiers, used by Alembic.
revision = '086cde3de7cf'
down_revision = None

import logging

from alembic import context
from alembic import op
from oslo_serialization import jsonutils
import sqlalchemy as sa

from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.extensions.consts import extensions_migration_buffer_table_name
from nailgun.extensions.utils import is_buffer_table_exist

logger = logging.getLogger('alembic.migration')
config = context.config
table_prefix = config.get_main_option('table_prefix')
table_volumes_name = '{0}node_volumes'.format(table_prefix)


def migrate_data_from_core(connection):
    if not is_buffer_table_exist(connection):
        # NOTE(eli): if there is no buffer table it means that there
        # is no core database we should not run data migrations includes
        # this case because extension might be installed and used
        # separately from Nailgun core and its database
        logger.warn(
            "Cannot find buffer table '{0}'. "
            "Don't run data migrations from buffer table, "
            "because extension might be installed and used "
            "separately from Nailgun core and its database".format(
                extensions_migration_buffer_table_name))
        return

    ext_name = 'volume_manager'

    select_query = sa.sql.text(
        'SELECT id, data FROM {0} '
        'WHERE extension_name=:extension_name'.format(
            extensions_migration_buffer_table_name))

    delete_query = sa.sql.text(
        'DELETE FROM {0} WHERE id=:record_id'.format(
            extensions_migration_buffer_table_name))

    insert_query = sa.sql.text(
        "INSERT INTO {0} (node_id, volumes)"
        "VALUES (:node_id, :volumes)".format(
            table_volumes_name))

    for buffer_record_id, volumes_data in connection.execute(
            select_query,
            extension_name=ext_name):

        volumes_parsed = jsonutils.loads(volumes_data)
        volumes = volumes_parsed.get('volumes')
        node_id = volumes_parsed.get('node_id')

        connection.execute(
            insert_query,
            node_id=node_id,
            volumes=jsonutils.dumps(volumes))

        connection.execute(
            delete_query,
            record_id=buffer_record_id)


def upgrade():
    connection = op.get_bind()

    op.create_table(
        table_volumes_name,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('volumes', JSON(), server_default='[]', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('node_id'))

    migrate_data_from_core(connection)


def downgrade():
    op.drop_table(table_volumes_name)
