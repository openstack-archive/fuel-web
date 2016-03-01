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

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from sqlalchemy.ext.mutable import MutableDict

from nailgun import consts

from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON


class DeploymentHistory(Base):
    __tablename__ = 'deployment_histories'
    __table_args__ = (
        UniqueConstraint(
            'task_id',
            'node_id',
            'deployment_graph_task_name',
            name='_task_id_node_id_deployment_graph_task_name_uc'),
    )

    id = Column(Integer, primary_key=True)
    task_id = Column(
        Integer,
        ForeignKey('tasks.id', ondelete='CASCADE'),
        nullable=False)
    deployment_graph_task_name = Column(String, nullable=False)
    node_id = Column(String, nullable=False)
    time_start = Column(DateTime, nullable=True)
    time_end = Column(DateTime, nullable=True)
    status = Column(
        Enum(*consts.TASK_STATUSES, name='deployment_history_task_status'),
        nullable=False,
        default=consts.TASK_STATUSES.pending)

    custom = Column(MutableDict.as_mutable(JSON), default={})
