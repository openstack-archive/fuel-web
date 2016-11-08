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

from nailgun import consts
from nailgun.db.sqlalchemy.models import fields


# revision identifiers, used by Alembic.
revision = 'dc8bc8751c42'
down_revision = 'c6edea552f1e'

q_select_release_query = sa.sql.text(
    "SELECT id, roles_metadata FROM releases "
    "WHERE roles_metadata IS NOT NULL"
)
q_update_release_query = sa.sql.text(
    "UPDATE releases SET roles_metadata = :roles_metadata WHERE id = :id")
q_select_plugin_query = sa.sql.text(
    "SELECT id, roles_metadata FROM plugins "
    "WHERE roles_metadata IS NOT NULL"
)
q_update_plugin_query = sa.sql.text(
    "UPDATE plugins SET roles_metadata = :roles_metadata WHERE id = :id")


def upgrade():
    upgrade_plugins_tags()
    upgrade_cluster_roles()


def downgrade():
    downgrade_cluster_roles()
    downgrade_plugins_tags()


def _create_tags(conn, select_query, update_query, owner_type):
    tag_create_query = sa.sql.text(
        "INSERT INTO tags (tag, owner_id, owner_type, has_primary, read_only) "
        "VALUES(:tag, :owner_id, :owner_type, :has_primary, true) RETURNING id"
    )
    for id, roles_metadata in conn.execute(select_query):
        roles_metadata = jsonutils.loads(roles_metadata)
        for role_name, role_metadata in six.iteritems(roles_metadata):
            conn.execute(
                tag_create_query,
                tag=role_name,
                owner_id=id,
                owner_type=owner_type,
                has_primary=roles_metadata.get('has_primary', False)
            )
        conn.execute(
            update_query,
            id=id,
            roles_metadata=jsonutils.dumps(roles_metadata),
        )


def _upgrade_tags_assignment(conn, node_query, owner_type):
    tag_assign_query = sa.sql.text(
        "INSERT INTO node_tags (node_id, tag_id, is_primary) "
        "VALUES(:node_id, :tag_id, :is_primary)"
    )
    tag_select_query = sa.sql.text(
        "SELECT id FROM tags WHERE owner_id=:id AND "
        "owner_type=:owner_type AND tag=:tag"
    )
    for id, role, primary_roles, owner_id in conn.execute(node_query):
        tag = conn.execute(
            tag_select_query,
            id=owner_id,
            owner_type=owner_type,
            tag=role
        ).fetchone()

        if not tag:
            continue

        conn.execute(
            tag_assign_query,
            node_id=id,
            tag_id=tag.id,
            is_primary=role in primary_roles
        )


def _upgrade_roles_metadata(conn, select_query, update_query):
    for id, roles_metadata in conn.execute(select_query):
        roles_metadata = jsonutils.loads(roles_metadata)
        for role_name, role_metadata in six.iteritems(roles_metadata):
            role_metadata['tags'] = [role_name]
        conn.execute(
            update_query,
            id=id,
            roles_metadata=jsonutils.dumps(roles_metadata),
        )


def _downgrade_roles_metadata(conn, select_query, update_query):
    for id, roles_metadata in conn.execute(select_query):
        roles_metadata = jsonutils.loads(roles_metadata)
        for role_name, role_metadata in six.iteritems(roles_metadata):
            del role_metadata['tags']
        conn.execute(
            update_query,
            id=id,
            roles_metadata=jsonutils.dumps(roles_metadata),
        )


def upgrade_plugins_tags():
    upgrade_plugins_table()
    upgrade_tags_existing_nodes()


def upgrade_tags_existing_nodes():
    connection = op.get_bind()
    node_plugin_query = sa.sql.text(
        "SELECT n.id as n_id, unnest(roles || pending_roles) AS role, "
        "primary_roles, p.id AS plugin_id FROM nodes n "
        "JOIN clusters c ON n.cluster_id=c.id "
        "JOIN cluster_plugins cp ON cp.cluster_id=c.id "
        "JOIN plugins p ON cp.plugin_id=p.id"
    )

    # Create tags for all plugins roles
    _create_tags(
        connection,
        q_select_plugin_query,
        q_update_plugin_query,
        consts.TAG_OWNER_TYPES.plugin
    )
    # for releases
    _upgrade_roles_metadata(connection,
                            q_select_release_query,
                            q_update_release_query)
    # for plugins
    _upgrade_roles_metadata(connection,
                            q_select_plugin_query,
                            q_update_plugin_query)
    # update tag's assignment for plugin tags
    _upgrade_tags_assignment(connection,
                             node_plugin_query,
                             consts.TAG_OWNER_TYPES.plugin)


def upgrade_plugins_table():
    op.add_column(
        'plugins',
        sa.Column('tags_metadata',
                  fields.JSON(),
                  nullable=False,
                  server_default='{}'),
    )


def downgrade_plugins_tags():
    connection = op.get_bind()
    # for releases
    _downgrade_roles_metadata(connection,
                              q_select_release_query,
                              q_update_release_query)
    # for plugins
    _downgrade_roles_metadata(connection,
                              q_select_plugin_query,
                              q_update_plugin_query)
    op.drop_column('plugins', 'tags_metadata')


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
