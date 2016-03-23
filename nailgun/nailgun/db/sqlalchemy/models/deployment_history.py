# -*- coding: utf-8 -*-

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

import sqlalchemy as sa

from sqlalchemy.ext.mutable import MutableDict

from nailgun import consts

from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON


class DeploymentHistory(Base):
    __tablename__ = 'deployment_history'
    __table_args__ = (
        sa.UniqueConstraint(
            'task_id',
            'node_id',
            'deployment_graph_task_name',
            name='_task_id_node_id_deployment_graph_task_name_uc'),
    )

    id = sa.Column(sa.Integer, primary_key=True)
    task_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('tasks.id', ondelete='CASCADE'),
        nullable=False)
    deployment_graph_task_name = sa.Column(sa.String, nullable=False)
    # String, because history need to be saved tasks for master and None nodes
    node_id = sa.Column(sa.String)
    time_start = sa.Column(sa.DateTime, nullable=True)
    time_end = sa.Column(sa.DateTime, nullable=True)
    status = sa.Column(
        sa.Enum(*consts.HISTORY_TASK_STATUSES,
                name='history_task_statuses'),
        nullable=False,
        default=consts.HISTORY_TASK_STATUSES.pending)

    custom = sa.Column(MutableDict.as_mutable(JSON), default={},
                       server_default='{}', nullable=False)
