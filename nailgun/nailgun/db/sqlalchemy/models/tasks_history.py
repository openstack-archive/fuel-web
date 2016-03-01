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
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text

from nailgun.db.sqlalchemy.models.base import Base


class TasksHistory(Base):
    __tablename__ = 'tasks_history'
    id = Column(Integer, primary_key=True)
    deployment_task_id = Column(Integer, ForeignKey('tasks.id'), ondelete='CASCADE')
    node_id = Column(Integer, ForeignKey('nodes.id'), ondelete='CASCADE')
    task_name = Column(Text, nullable=False)
    time_started = Column(DateTime, nullable=True)
    time_ended = Column(DateTime, nullable=True)
    status = Column(
        Enum(*consts.TASK_STATUSES, name='task_status'),
        nullable=False,
        default=consts.TASK_STATUSES.pending
    )
