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
from oslo_serialization import jsonutils

import six
import sqlalchemy as sa

from nailgun import consts
from nailgun.db.sqlalchemy.models import fields
from nailgun.utils.migration import drop_enum


# revision identifiers, used by Alembic.
revision = 'c6edea552f1e'
down_revision = 'f2314e5d63c9'


def upgrade():
    upgrade_plugin_links_constraints()
    upgrade_release_required_component_types()
    upgrade_components_tagging()
    upgrade_tags_existing_nodes()


def downgrade():
    downgrade_components_tagging()
    downgrade_release_required_component_types()
    downgrade_plugin_links_constraints()


def _create_tags(conn, select_query, update_query, owner_type):
    tag_create_query = sa.sql.text(
        "INSERT INTO tags (tag, owner_id, owner_type, has_primary, read_only) "
        "VALUES(:tag, :owner_id, :owner_type, :has_primary, true) RETURNING id"
    )
    for id, roles_metadata in conn.execute(select_query):
        roles_metadata = jsonutils.loads(roles_metadata)
        for role_name, role_metadata in six.iteritems(roles_metadata):
            role_metadata['tags'] = [role_name]
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


def _update_tags_assignment(conn, node_query, owner_type):
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


def upgrade_tags_existing_nodes():
    connection = op.get_bind()
    node_rel_query = sa.sql.text(
        "SELECT n.id as n_id, unnest(roles || pending_roles) AS role, "
        "primary_roles, r.id AS release_id FROM nodes n "
        "JOIN clusters c ON n.cluster_id=c.id "
        "JOIN releases r ON r.id=c.release_id"
    )
    node_plugin_query = sa.sql.text(
        "SELECT n.id as n_id, unnest(roles || pending_roles) AS role, "
        "primary_roles, p.id AS plugin_id FROM nodes n "
        "JOIN clusters c ON n.cluster_id=c.id "
        "JOIN cluster_plugins cp ON cp.cluster_id=c.id "
        "JOIN plugins p ON cp.plugin_id=p.id"
    )
    select_release_query = sa.sql.text(
        "SELECT id, roles_metadata FROM releases "
        "WHERE roles_metadata IS NOT NULL"
    )
    update_release_query = sa.sql.text(
        "UPDATE releases SET roles_metadata = :roles_metadata WHERE id = :id")
    select_plugin_query = sa.sql.text(
        "SELECT id, roles_metadata FROM plugins "
        "WHERE roles_metadata IS NOT NULL"
    )
    update_plugin_query = sa.sql.text(
        "UPDATE plugins SET roles_metadata = :roles_metadata WHERE id = :id")

    # Create tags for all release roles
    _create_tags(
        connection,
        select_release_query,
        update_release_query,
        consts.TAG_OWNER_TYPES.release
    )

    # Create tags for all plugins roles
    _create_tags(
        connection,
        select_plugin_query,
        update_plugin_query,
        consts.TAG_OWNER_TYPES.plugin
    )
    # update tag's assignment for release tags
    _update_tags_assignment(connection,
                            node_rel_query,
                            consts.TAG_OWNER_TYPES.release)
    # update tag's assignment for plugin tags
    _update_tags_assignment(connection,
                            node_plugin_query,
                            consts.TAG_OWNER_TYPES.plugin)


def upgrade_components_tagging():
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tag', sa.String(64), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column(
            'owner_type',
            sa.Enum(
                *consts.TAG_OWNER_TYPES,
                name='tag_owner_type'),
            nullable=False),
        sa.Column('has_primary', sa.Boolean),
        sa.Column('read_only', sa.Boolean),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'owner_type', 'owner_id', 'tag',
            name='__tag_owner_uc'),
    )

    op.create_table(
        'node_tags',
        sa.Column('id', sa.Integer()),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.Column('is_primary', sa.Boolean, default=False),
        sa.ForeignKeyConstraint(
            ['node_id'], ['nodes.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['tag_id'], ['tags.id'], ondelete='CASCADE'
        )
    )
    op.add_column(
        'releases',
        sa.Column('tags_metadata', fields.JSON(), nullable=True),
    )
    op.add_column(
        'plugins',
        sa.Column('tags_metadata',
                  fields.JSON(),
                  nullable=True,
                  server_default='{}'),
    )


def downgrade_components_tagging():
    op.drop_table('node_tags')
    op.drop_table('tags')
    drop_enum('tag_owner_type')
    op.drop_column('releases', 'tags_metadata')
    op.drop_column('plugins', 'tags_metadata')


def upgrade_plugin_links_constraints():
    connection = op.get_bind()

    # plugin links
    plugin_links_remove_duplicates_query = sa.text("""
        DELETE FROM plugin_links
        WHERE id
        NOT IN (
          SELECT MIN(id)
          FROM plugin_links
          GROUP BY url
        )
    """)
    connection.execute(plugin_links_remove_duplicates_query)

    op.create_unique_constraint(
        'plugin_links_url_uc',
        'plugin_links',
        ['url'])

    # cluster plugin links
    cluster_plugin_links_remove_duplicates_query = sa.text("""
        DELETE FROM cluster_plugin_links
        WHERE id
        NOT IN (
          SELECT MIN(id)
          FROM cluster_plugin_links
          GROUP BY cluster_id,url
        )
    """)
    connection.execute(cluster_plugin_links_remove_duplicates_query)

    op.create_unique_constraint(
        'cluster_plugin_links_cluster_id_url_uc',
        'cluster_plugin_links',
        ['cluster_id', 'url'])


def downgrade_plugin_links_constraints():
    op.drop_constraint('cluster_plugin_links_cluster_id_url_uc',
                       'cluster_plugin_links')

    op.drop_constraint('plugin_links_url_uc', 'plugin_links')


def upgrade_release_required_component_types():
    op.add_column(
        'releases',
        sa.Column(
            'required_component_types',
            fields.JSON(),
            nullable=False,
            server_default='[]'
        )
    )
    connection = op.get_bind()
    connection.execute(
        sa.sql.text(
            "UPDATE releases SET required_component_types = :required_types"),
        required_types=jsonutils.dumps(['hypervisor', 'network', 'storage'])
    )


def downgrade_release_required_component_types():
    op.drop_column('releases', 'required_component_types')
