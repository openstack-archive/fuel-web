"""fuel_5_1.py

Revision ID: 68a719cd08e
Revises: 1398619bdf8c
Create Date: 2014-06-03 11:54:26.000960

"""

# revision identifiers, used by Alembic.
revision = '68a719cd08e'
down_revision = '1398619bdf8c'

from alembic import op
import sqlalchemy as sa

from nailgun.utils.migration import upgrade_enum


old_network_group_name = (
    'fuelweb_admin',
    'storage',
    'management',
    'public',
    'floating',
    'fixed',
    'private',
)
new_network_group_name = (
    old_network_group_name + (
        'mesh',
    )
)


def upgrade():
    op.add_column('neutron_config', sa.Column(
        'gre_network', sa.String(30), nullable=False
    ))
    upgrade_enum(
        "network_groups",            # table
        "name",                      # column
        "network_group_name",        # ENUM name
        old_network_group_name,      # old options
        new_network_group_name,      # new options
    )


def downgrade():
    op.drop_column('neutron_config', 'gre_network')
    upgrade_enum(
        "network_groups",            # table
        "name",                      # column
        "network_group_name",        # ENUM name
        new_network_group_name,      # new options
        old_network_group_name,      # old options
    )
