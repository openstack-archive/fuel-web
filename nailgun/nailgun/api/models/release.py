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
from sqlalchemy import Enum
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Unicode
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import relationship

from nailgun.api.models.base import Base
from nailgun.api.models.fields import JSON
from nailgun.api.models.node import Role
from nailgun.db import db


class Release(Base):
    __tablename__ = 'releases'
    __table_args__ = (
        UniqueConstraint('name', 'version'),
    )
    STATES = (
        'not_available',
        'downloading',
        'error',
        'available'
    )
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(100), nullable=False)
    version = Column(String(30), nullable=False)
    description = Column(Unicode)
    operating_system = Column(String(50), nullable=False)
    state = Column(Enum(*STATES, name='release_state'),
                   nullable=False,
                   default='not_available')
    networks_metadata = Column(JSON, default=[])
    attributes_metadata = Column(JSON, default={})
    volumes_metadata = Column(JSON, default={})
    modes_metadata = Column(JSON, default={})
    roles_metadata = Column(JSON, default={})
    role_list = relationship(
        "Role",
        backref="release",
        cascade="all,delete"
    )
    clusters = relationship(
        "Cluster",
        backref="release",
        cascade="all,delete"
    )

    @property
    def roles(self):
        return [role.name for role in self.role_list]

    @roles.setter
    def roles(self, roles):
        new_roles = set(roles)
        for role in self.role_list:
            if role.name not in new_roles:
                db().delete(role)
            else:
                new_roles.remove(role.name)
        for new_role in new_roles:
            self.role_list.append(
                Role(name=new_role, release=self)
            )
        db().commit()
