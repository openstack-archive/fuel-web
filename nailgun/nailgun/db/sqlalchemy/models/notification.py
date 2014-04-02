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

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text

from nailgun import consts

from nailgun.db.sqlalchemy.models.base import Base


class Notification(Base):
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True)
    cluster_id = Column(
        Integer,
        ForeignKey('clusters.id', ondelete='SET NULL')
    )
    node_id = Column(Integer, ForeignKey('nodes.id', ondelete='SET NULL'))
    task_id = Column(Integer, ForeignKey('tasks.id', ondelete='SET NULL'))
    topic = Column(
        Enum(*consts.NOTIFICATION_TOPICS, name='notif_topic'),
        nullable=False
    )
    message = Column(Text)
    status = Column(
        Enum(*consts.NOTIFICATION_STATUSES, name='notif_status'),
        nullable=False,
        default=consts.NOTIFICATION_STATUSES.unread
    )
    datetime = Column(DateTime, nullable=False)
