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
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from sqlalchemy.dialects import postgresql as psql

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base


class Component(Base):
    __tablename__ = 'components'
    __table_args__ = (
        UniqueConstraint('name', 'type', name='_component_name_type_uc'),
    )
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(
        Enum(*consts.COMPONENT_TYPES, name='component_types'),
        nullable=False
    )
    hypervisors = Column(psql.ARRAY(String), nullable=False, default=[],
                         server_default='{}')
    networks = Column(psql.ARRAY(String), nullable=False, default=[],
                      server_default='{}')
    storages = Column(psql.ARRAY(String), nullable=False, default=[],
                      server_default='{}')
    additional_services = Column(psql.ARRAY(String), nullable=False,
                                 default=[], server_default='{}')
    plugin_id = Column(Integer, ForeignKey('plugins.id', ondelete='CASCADE'))


class ReleaseComponents(Base):

    __tablename__ = 'release_components'
    id = Column(Integer, primary_key=True)
    release_id = Column(Integer, ForeignKey('releases.id', ondelete='CASCADE'),
                        nullable=False)
    component_id = Column(Integer, ForeignKey('components.id'), nullable=False)
