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
from sqlalchemy.orm import deferred

from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON


class NodeDeploymentInfo(Base):
    __tablename__ = 'node_deployment_info'
    __table_args__ = (
        sa.Index('node_deployment_info_task_id_and_node_uid',
                 'task_id', 'node_uid'),
    )

    id = sa.Column(sa.Integer, primary_key=True, nullable=False)
    task_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('tasks.id', ondelete='CASCADE'),
        nullable=False)

    node_uid = sa.Column(
        sa.String(20),
        nullable=True)

    deployment_info = deferred(sa.Column(MutableDict.as_mutable(JSON),
                                         nullable=True))
