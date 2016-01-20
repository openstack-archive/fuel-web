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
import yaml

from oslo_db.sqlalchemy import models
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import Integer
from sqlalchemy.orm.base import object_state

from nailgun.db import deadlock_detector as dd
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models import mutable as nailgun_mutable
from nailgun.settings import settings


class ObserverModelBase(models.ModelBase):
    """Model which traces modifications of DB objects."""

    def __setattr__(self, key, value):
        super(ObserverModelBase, self).__setattr__(key, value)
        state = object_state(self)
        # If object exists in the DB (have id) and attached to
        # the SqlAlchemy session (state.session_id is not None)
        # UPDATE query will be generated on SqlAlchemy session
        # flush or commit. Thus we should trace such DB object
        # modifications.
        if self.id is not None and state.session_id is not None:
            dd.handle_lock(self.__tablename__, ids=(self.id,))


if settings.DEVELOPMENT:
    Base = declarative_base(cls=ObserverModelBase)
else:
    Base = declarative_base(cls=models.ModelBase)


class CapacityLog(Base):
    __tablename__ = 'capacity_log'

    id = Column(Integer, primary_key=True)
    report = Column(MutableDict.as_mutable(JSON))
    datetime = Column(DateTime, default=lambda: datetime.now())


# Registering MutableDict representer for yaml safe dumper
yaml.SafeDumper.add_representer(
    nailgun_mutable.MutableDict,
    yaml.representer.SafeRepresenter.represent_dict
)

# Registering sqlalchemy.ext.mutable.MutableDict representer for yaml
# safe dumper
yaml.SafeDumper.add_representer(
    MutableDict,
    yaml.representer.SafeRepresenter.represent_dict
)

# Registering MutableList representer for yaml safe dumper
yaml.SafeDumper.add_representer(
    nailgun_mutable.MutableList,
    yaml.representer.SafeRepresenter.represent_list
)
