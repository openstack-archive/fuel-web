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

from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON


class Component(Base):
    __tablename__ = 'components'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    hypervisor = Column(JSON, server_default='[]', nullable=False)
    networking = Column(JSON, server_default='[]', nullable=False)
    storage = Column(JSON, server_default='[]', nullable=False)
    additional_services = Column(JSON, server_default='[]', nullable=False)
    plugin_id = Column(Integer, ForeignKey('plugins.id', ondelete='CASCADE'))
    release_id = Column(Integer, ForeignKey('releases.id', ondelete='CASCADE'))
