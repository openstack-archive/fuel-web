# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from nailgun.db.sqlalchemy.models.base import Base


class DashboardEntry(Base):
    __tablename__ = 'dashborad_entries'
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    title = Column(String(50), nullable=False)
    url = Column(Text, nullable=False)
    description = Column(Text)
