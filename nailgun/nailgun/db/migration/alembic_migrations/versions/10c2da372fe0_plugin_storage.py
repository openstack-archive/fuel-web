"""plugin_storage

Revision ID: 10c2da372fe0
Revises: 1a1504d469f8
Create Date: 2014-06-02 15:26:39.263073

"""

# revision identifiers, used by Alembic.
revision = '10c2da372fe0'
down_revision = '52924111f7d8'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from nailgun.utils.migration import drop_enum


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'plugin_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plugin', sa.String(length=150), nullable=True),
        sa.Column('record_type', sa.Enum(
            'role',
            'pending_role',
            'volume',
            'cluster_attribute',
            name='record_type'
        ), nullable=False),
        sa.Column('data', postgresql.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('plugin_records')
    drop_enum('record_type')
    ### end Alembic commands ###
