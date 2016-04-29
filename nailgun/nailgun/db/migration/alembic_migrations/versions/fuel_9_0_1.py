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

"""Fuel 9.0.1

Revision ID: 675105097a69
Revises: 11a9adc6d36a
Create Date: 2016-04-28 22:23:40.895589

"""

from alembic import op
import sqlalchemy as sa

from oslo_serialization import jsonutils

# revision identifiers, used by Alembic.
revision = '675105097a69'
down_revision = '11a9adc6d36a'

cgroups_attrs = {
    'metadata': {
        'label': 'Cgroups configuration for services',
        'weight': 90,
        'group': 'general',
        'always_editable': True,
        'restrictions': [{'condition': 'true', 'action': 'hide'}]
    }
}


def upgrade():
    upgrade_deployment_history()
    upgrade_cgroups_cluster_attrs()


def downgrade():
    downgrade_cgroups_cluster_attrs()
    downgrade_deployment_history()


def upgrade_deployment_history():
    op.create_index('deployment_history_task_name_status_idx',
                    'deployment_history',
                    ['deployment_graph_task_name', 'status'])


def downgrade_deployment_history():
    op.drop_index('deployment_history_task_name_status_idx',
                  'deployment_history')


def _update_cluster_editable_attrs(update_method):
    connection = op.get_bind()

    q_get_cluster_attrs = sa.text(
        "SELECT cluster_id, editable FROM attributes")
    q_update_cluster_attrs = sa.text(
        "UPDATE attributes "
        "SET editable = :editable "
        "WHERE cluster_id = :cluster_id")
    for cluster_id, editable in connection.execute(q_get_cluster_attrs):
        editable = jsonutils.loads(editable)
        update_method(editable)
        connection.execute(
            q_update_cluster_attrs,
            cluster_id=cluster_id,
            editable=jsonutils.dumps(editable)
        )


def upgrade_cgroups_cluster_attrs():
    def _update(editable):
        editable['cgroups'] = cgroups_attrs
    _update_cluster_editable_attrs(_update)


def downgrade_cgroups_cluster_attrs():
    def _update(editable):
        editable.pop('cgroups', None)
    _update_cluster_editable_attrs(_update)
