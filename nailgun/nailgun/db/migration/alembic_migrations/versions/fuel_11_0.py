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

"""Fuel 11.0

Revision ID: dc8bc8751c42
Revises: c6edea552f1e
Create Date: 2016-10-22 02:11:47.708895

"""

from alembic import op
from oslo_serialization import jsonutils
import six

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

from nailgun.db.sqlalchemy.models import fields


# revision identifiers, used by Alembic.
revision = 'dc8bc8751c42'
down_revision = 'c6edea552f1e'


def upgrade():
    upgrade_cluster_roles()
    upgrade_tags_meta()
    upgrade_primary_unit()


def downgrade():
    downgrade_primary_unit()
    downgrade_tags_meta()
    downgrade_cluster_roles()


def upgrade_cluster_roles():
    op.add_column(
        'clusters',
        sa.Column('roles_metadata',
                  fields.JSON(),
                  default={},
                  server_default='{}'),
    )
    op.add_column(
        'clusters',
        sa.Column('volumes_metadata',
                  fields.JSON(),
                  default={},
                  server_default='{}'),
    )


def downgrade_cluster_roles():
    op.drop_column('clusters', 'roles_metadata')
    op.drop_column('clusters', 'volumes_metadata')


def upgrade_tags_meta():
    connection = op.get_bind()
    op.add_column(
        'releases',
        sa.Column('tags_metadata',
                  fields.JSON(),
                  server_default='{}',
                  nullable=False),
    )
    op.add_column(
        'clusters',
        sa.Column('tags_metadata',
                  fields.JSON(),
                  server_default='{}',
                  nullable=False),
    )
    op.add_column(
        'plugins',
        sa.Column('tags_metadata',
                  fields.JSON(),
                  server_default='{}',
                  nullable=False),
    )

    q_get_role_meta = "SELECT id, roles_metadata FROM {}"
    q_update_tags_meta = ("UPDATE {} SET tags_metadata = :tags_meta "
                          "WHERE id = :obj_id")
    q_update_roles_meta = ("UPDATE {} SET roles_metadata = :roles_meta "
                           "WHERE id = :obj_id")

    for table in ['releases', 'plugins']:
        for obj_id, roles_meta in connection.execute(
                sa.text(q_get_role_meta.format(table))):
            tags_meta = {}
            roles_meta = jsonutils.loads(roles_meta)
            for role_name, meta in six.iteritems(roles_meta):
                meta['tags'] = [role_name]
                tags_meta[role_name] = {'has_primary': meta.get('has_primary',
                                                                False)}
            connection.execute(sa.text(q_update_roles_meta.format(table)),
                               roles_meta=jsonutils.dumps(roles_meta),
                               obj_id=obj_id)
            connection.execute(sa.text(q_update_tags_meta.format(table)),
                               tags_meta=jsonutils.dumps(tags_meta),
                               obj_id=obj_id)


def downgrade_tags_meta():
    op.drop_column('releases', 'tags_metadata')
    op.drop_column('clusters', 'tags_metadata')
    op.drop_column('plugins', 'tags_metadata')


def upgrade_primary_unit():
    op.alter_column('nodes', 'primary_roles', new_column_name='primary_tags')


def downgrade_primary_unit():
    connection = op.get_bind()
    op.add_column(
        'nodes',
        sa.Column('primary_roles',
                  psql.ARRAY(sa.String(64)),
                  default=[],
                  server_default='{}',
                  nullable=False)
    )
    q_get_roles = sa.text('''
        SELECT id, roles, pending_roles, primary_tags
        FROM nodes
    ''')
    q_update_primary_roles = sa.text('''
        UPDATE nodes
        SET primary_roles = :primary_roles
        WHERE id = :node_id
    ''')
    for node_id, roles, p_roles, pr_tags in connection.execute(q_get_roles):
        primary_roles = list(set(roles + p_roles) & set(pr_tags))
        connection.execute(
            q_update_primary_roles,
            node_id=node_id,
            primary_roles=primary_roles
        )
    op.drop_column('nodes', 'primary_tags')
