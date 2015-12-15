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


from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy.dialects import postgresql
from sqlalchemy import Enum
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import Time
from sqlalchemy import UniqueConstraint

from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON

from nailgun import consts


class OpenStackWorkloadStats(Base):
    __tablename__ = 'oswl_stats'
    __table_args__ = (
        UniqueConstraint('cluster_id', 'created_date', 'resource_type'),
    )

    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, nullable=False, index=True)

    created_date = Column(Date, nullable=False, index=True)
    updated_time = Column(Time, nullable=False)

    resource_type = Column(
        Enum(*consts.OSWL_RESOURCE_TYPES, name='oswl_resource_type'),
        nullable=False,
        index=True
    )

    resource_data = Column(JSON, nullable=True)

    resource_checksum = Column(Text, nullable=False)
    is_sent = Column(Boolean, nullable=False, default=False, index=True)
    version_info = Column(MutableDict.as_mutable(postgresql.JSON),
                          nullable=True, default={}, server_default='{}')
