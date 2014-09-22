#    Copyright 2014 Mirantis, Inc.
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
from sqlalchemy import Integer
from sqlalchemy import String

from nailgun.db.sqlalchemy.models.base import Base


class ActionLogs(Base):
    __tablename__ = 'action_logs'

    id = Column(Integer, primary_key=True)
    actor_id = Column(String(64), nullable=False)
    action_group = Column(String(64), nullable=False)
    action_name = Column(String(64), nullable=False)
