"""fuel_5_1.py

Revision ID: 68a719cd08e
Revises: 1a1504d469f8
Create Date: 2014-06-03 11:54:26.000960

"""

# revision identifiers, used by Alembic.
revision = '68a719cd08e'
down_revision = '1a1504d469f8'

from alembic import op
import sqlalchemy as sa


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


def upgrade_enum(table, column_name, enum_name, old_options, new_options):
    old_type = sa.Enum(*old_options, name=enum_name)
    new_type = sa.Enum(*new_options, name=enum_name)
    tmp_type = sa.Enum(*new_options, name="_" + enum_name)
    # Create a temporary type, convert and drop the "old" type
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        u'ALTER TABLE {0} ALTER COLUMN {1} TYPE _{2}'
        u' USING {1}::text::_{2}'.format(
            table,
            column_name,
            enum_name
        )
    )
    old_type.drop(op.get_bind(), checkfirst=False)
    # Create and convert to the "new" type
    new_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        u'ALTER TABLE {0} ALTER COLUMN {1} TYPE {2}'
        u' USING {1}::text::{2}'.format(
            table,
            column_name,
            enum_name
        )
    )
    tmp_type.drop(op.get_bind(), checkfirst=False)


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
