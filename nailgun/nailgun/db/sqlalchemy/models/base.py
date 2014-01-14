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

from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer

from sqlalchemy.ext.declarative import declarative_base

from nailgun.db.sqlalchemy.models.fields import JSON


Base = declarative_base()


def list_attrs(names, o):
    from UserString import MutableString
    out_str = MutableString()
    longest_name = sorted(names, key=len, reverse=True)[0]
    column_width = len(longest_name)
    for n in names:
        spacer = " " * (column_width - len(n))
        out_str += (n + spacer + " : ")
        out_str += (getattr(o, n).__repr__() + "\n")
    return out_str


class GlobalParameters(Base):
    __tablename__ = 'global_parameters'
    id = Column(Integer, primary_key=True)
    parameters = Column(JSON, default={})

    def __repr__(self):
        return "GlobalParameters\n" + list_attrs(["id", "parameters"], self).__str__()

class CapacityLog(Base):
    __tablename__ = 'capacity_log'

    id = Column(Integer, primary_key=True)
    report = Column(JSON)
    datetime = Column(DateTime, default=datetime.now())

    def __repr__(self):
        return "CapacityLog\n" + list_attrs(["id", "report", "datetime"], self).__str__()
