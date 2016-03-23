# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import uuid

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import relationship, backref, deferred

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.mutable import MutableDict


class Task(Base):
    __tablename__ = 'tasks'
    __table_args__ = (
        Index('cluster_name_idx', 'cluster_id', 'name'),
    )

    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id', ondelete='CASCADE'))
    uuid = Column(String(36), nullable=False,
                  default=lambda: str(uuid.uuid4()))
    name = Column(
        Enum(*consts.TASK_NAMES, name='task_name'),
        nullable=False,
        default='super'
    )
    message = Column(Text)
    status = Column(
        Enum(*consts.TASK_STATUSES, name='task_status'),
        nullable=False,
        default='running'
    )
    progress = Column(Integer, default=0)
    cache = deferred(Column(MutableDict.as_mutable(JSON), default={}))
    # By design 'result' value accept dict and list types
    # depends on task type. Don't do this field MutableDict.
    result = Column(JSON, default={})
    parent_id = Column(Integer, ForeignKey('tasks.id', ondelete='CASCADE'))
    subtasks = relationship(
        "Task",
        backref=backref('parent', remote_side=[id]),
        cascade="all,delete"
    )
    notifications = relationship(
        "Notification",
        backref=backref('task', remote_side=[id])
    )
    # Task weight is used to calculate supertask progress
    # sum([t.progress * t.weight for t in supertask.subtasks]) /
    # sum([t.weight for t in supertask.subtasks])
    weight = Column(Float, default=1.0)
    deleted_at = Column(DateTime)

    deployment_info = Column(MutableDict.as_mutable(JSON), nullable=True)
    cluster_settings = Column(MutableDict.as_mutable(JSON), nullable=True)
    network_settings = Column(MutableDict.as_mutable(JSON), nullable=True)

    deployment_history = relationship(
        "DeploymentHistory", backref="task", cascade="all,delete")

    def __repr__(self):
        return "<Task '{0}' {1} ({2}) {3}>".format(
            self.name,
            self.uuid,
            self.cluster_id,
            self.status
        )

    def create_subtask(self, name, **kwargs):
        if not name:
            raise ValueError("Subtask name not specified")

        task = Task(name=name, cluster=self.cluster, **kwargs)
        self.subtasks.append(task)
        db().flush()
        return task

    def is_completed(self):
        return self.status == consts.TASK_STATUSES.error or \
            self.status == consts.TASK_STATUSES.ready
