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

from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.base import list_attrs


class Plugin(Base):
    __tablename__ = 'plugins'
    TYPES = ('nailgun', 'fuel')

    id = Column(Integer, primary_key=True)
    type = Column(Enum(*TYPES, name='plugin_type'), nullable=False)
    name = Column(String(128), nullable=False, unique=True)
    state = Column(String(128), nullable=False, default='registered')
    version = Column(String(128), nullable=False)

    def __repr__(self):
        return "Plugin\n" + list_attrs(["id", "type", "name", "state",
                                        "version"], self).__str__()
