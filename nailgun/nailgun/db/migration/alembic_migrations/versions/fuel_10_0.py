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
from nailgun.db.sqlalchemy.models import fields
from nailgun.utils.migration import upgrade_enum
from oslo_serialization import jsonutils
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6edea552f1e'
down_revision = '3763c404ca48'

cluster_changes_old = (
    'networks',
    'attributes',
    'disks',
    'interfaces',
    'vmware_attributes'
)
cluster_changes_new = (
    'networks',
    'attributes',
    'disks',
    'interfaces',
)


def upgrade():
    upgrade_plugin_links_constraints()
    upgrade_release_required_component_types()
    upgrade_remove_vmware()


def downgrade():
    downgrade_remove_vmware()
    downgrade_release_required_component_types()
    downgrade_plugin_links_constraints()


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


def upgrade_remove_vmware():
    connection = op.get_bind()
    op.drop_constraint(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes',
        type_='foreignkey'
    )
    op.drop_table('vmware_attributes')
    op.drop_column('releases', 'vmware_attributes_metadata')
    delete = sa.sql.text(
        """DELETE FROM cluster_changes
        WHERE name = 'vmware_attributes'""")
    connection.execute(delete)
    upgrade_enum(
        "cluster_changes",          # table
        "name",                     # column
        "possible_changes",         # ENUM name
        cluster_changes_old,        # old options
        cluster_changes_new         # new options
    )


def downgrade_remove_vmware():
    op.add_column(
        'releases',
        sa.Column('vmware_attributes_metadata', fields.JSON(), nullable=True))

    op.create_table(
        'vmware_attributes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cluster_id', sa.Integer()),
        sa.Column('editable', fields.JSON()),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ),
        sa.PrimaryKeyConstraint('id'))

    upgrade_enum(
        "cluster_changes",          # table
        "name",                     # column
        "possible_changes",         # ENUM name
        cluster_changes_new,        # new options
        cluster_changes_old         # old options
    )

    op.drop_constraint(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes',
        type_='foreignkey'
    )

    op.create_foreign_key(
        'vmware_attributes_cluster_id_fkey',
        'vmware_attributes', 'clusters',
        ['cluster_id'], ['id'],
        ondelete='CASCADE'
    )
