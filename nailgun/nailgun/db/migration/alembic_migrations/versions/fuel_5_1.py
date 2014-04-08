"""fuel_5_1

Revision ID: 1398619bdf8c
Revises: 1a1504d469f8
Create Date: 2014-05-30 14:46:55.496697

"""

# revision identifiers, used by Alembic.
revision = '1398619bdf8c'
down_revision = '1a1504d469f8'

from alembic import op
import sqlalchemy as sa

from nailgun import consts
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.utils.migration import upgrade_enum


task_names_old = ('super', 'deploy', 'deployment',
                  'provision', 'stop_deployment',
                  'reset_environment',
                  'node_deletion',
                  'cluster_deletion',
                  'check_before_deployment',
                  'check_networks',
                  'verify_networks', 'check_dhcp',
                  'verify_network_connectivity',
                  'redhat_setup',
                  'redhat_check_credentials',
                  'redhat_check_licenses',
                  'redhat_download_release',
                  'redhat_update_cobbler_profile',
                  'dump', 'capacity_log')

task_names_new = consts.TASK_NAMES

cluster_statuses_old = ('new', 'deployment', 'stopped',
                        'operational', 'error', 'remove')

cluster_statuses_new = consts.CLUSTER_STATUSES


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('releases',
                  sa.Column('can_update_from_versions',
                            JSON(),
                            nullable=False))
    op.add_column('clusters',
                  sa.Column('pending_release_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_pending_release_id',
                          'clusters',
                          'releases',
                          ['pending_release_id'],
                          ['id'], )
    upgrade_enum(
        "clusters",  # table
        "status",  # column
        "cluster_status",  # ENUM name
        cluster_statuses_old,  # old options
        cluster_statuses_new  # new options
    )
    upgrade_enum(
        "tasks",  # table
        "name",  # column
        "task_name",  # ENUM name
        task_names_old,  # old options
        task_names_new  # new options
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    upgrade_enum(
        "tasks",  # table
        "name",  # column
        "task_name",  # ENUM name
        task_names_new,  # old options
        task_names_old  # new options
    )
    upgrade_enum(
        "clusters",  # table
        "status",  # column
        "cluster_status",  # ENUM name
        cluster_statuses_new,  # old options
        cluster_statuses_old  # new options
    )
    op.drop_constraint('pending_release_id',
                       'clusters',
                       type_='foreignkey')
    op.drop_column('clusters', 'pending_release_id')
    op.drop_column('releases', 'can_update_from_versions')
    ### end Alembic commands ###
