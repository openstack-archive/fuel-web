"""fuel_5_1

Revision ID: 16ba5d64a8d9
Revises: 1a1504d469f8
Create Date: 2014-06-02 13:57:36.987212

"""

# revision identifiers, used by Alembic.
revision = '16ba5d64a8d9'
down_revision = '1a1504d469f8'

from alembic import op
import sqlalchemy as sa


old_notification_topics = (
    'discover',
    'done',
    'error',
    'warning',
)
new_notification_topics = (
    old_notification_topics + (
        'release',
    )
)


def upgrade_enum(table, column_name, enum_name, old_options, new_options):
    old_type = sa.Enum(*old_options, name=enum_name)
    new_type = sa.Enum(*new_options, name=enum_name)
    tmp_type = sa.Enum(*new_options, name="_" + enum_name)

    # Create a tempoary type, convert and drop the "old" type
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
    upgrade_enum(
        "notifications",             # table
        "topic",                     # column
        "notif_topic",               # ENUM name
        old_notification_topics,     # old options
        new_notification_topics,     # new options
    )


def downgrade():
    upgrade_enum(
        "notifications",             # table
        "topic",                     # column
        "notif_topic",               # ENUM name
        new_notification_topics,     # new options
        old_notification_topics,     # old options
    )
