"""add multicast task

Revision ID: e5f529584c2
Revises: 4f21f21e2672
Create Date: 2014-03-17 12:46:03.959014

"""

# revision identifiers, used by Alembic.
revision = 'e5f529584c2'
down_revision = '4f21f21e2672'


from nailgun.db.migration import utils

new_task_names = ('multicast',)


def upgrade():
    utils.enum_select_and_upgrade("tasks", "name", "task_name", new_task_names)


def downgrade():
    utils.enum_select_and_downgrade("tasks", "name",
                                    "task_name", new_task_names)
