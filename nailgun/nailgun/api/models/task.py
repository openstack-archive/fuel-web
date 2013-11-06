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
from sqlalchemy import Enum
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import relationship, backref

from nailgun.api.models.base import Base
from nailgun.api.models.fields import JSON
from nailgun.db import db


class Task(Base):
    __tablename__ = 'tasks'
    TASK_STATUSES = (
        'ready',
        'running',
        'error'
    )
    TASK_NAMES = (
        'super',

        # cluster
        'deployment',
        # For deployment supertask, it contains
        # two subtasks deployment and provision
        'deploy',
        'provision',
        'node_deletion',
        'cluster_deletion',
        'check_before_deployment',

        # network
        'check_networks',
        'verify_networks',
        'check_dhcp',
        'verify_network_connectivity',

        # plugin
        'install_plugin',
        'update_plugin',
        'delete_plugin',

        # red hat
        'redhat_setup',
        'redhat_check_credentials',
        'redhat_check_licenses',
        'redhat_download_release',
        'redhat_update_cobbler_profile',

        # dump
        'dump',

        'capacity_log'
    )
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    uuid = Column(String(36), nullable=False,
                  default=lambda: str(uuid.uuid4()))
    name = Column(
        Enum(*TASK_NAMES, name='task_name'),
        nullable=False,
        default='super'
    )
    message = Column(Text)
    status = Column(
        Enum(*TASK_STATUSES, name='task_status'),
        nullable=False,
        default='running'
    )
    progress = Column(Integer, default=0)
    cache = Column(JSON, default={})
    result = Column(JSON, default={})
    parent_id = Column(Integer, ForeignKey('tasks.id'))
    subtasks = relationship(
        "Task",
        backref=backref('parent', remote_side=[id])
    )
    notifications = relationship(
        "Notification",
        backref=backref('task', remote_side=[id])
    )
    # Task weight is used to calculate supertask progress
    # sum([t.progress * t.weight for t in supertask.subtasks]) /
    # sum([t.weight for t in supertask.subtasks])
    weight = Column(Float, default=1.0)

    def __repr__(self):
        return "<Task '{0}' {1} ({2}) {3}>".format(
            self.name,
            self.uuid,
            self.cluster_id,
            self.status
        )

    def create_subtask(self, name):
        if not name:
            raise ValueError("Subtask name not specified")

        task = Task(name=name, cluster=self.cluster)

        self.subtasks.append(task)
        db().commit()
        return task
