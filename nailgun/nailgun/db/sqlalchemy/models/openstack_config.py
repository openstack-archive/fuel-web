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

from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON


class OpenstackConfig(Base):
    __tablename__ = 'openstack_configs'

    id = Column(Integer, primary_key=True)
    is_active = Column(Boolean, nullable=False, default=True)
    config_type = Column(
        Enum(*consts.OPENSTACK_CONFIG_TYPES, name='openstack_config_types'),
        nullable=False)

    # asaprykin: In case there will be global configuration
    # nullable should be set to 'True'
    cluster_id = Column(
        Integer,
        ForeignKey('clusters.id', ondelete='CASCADE'),
        nullable=False
    )
    node_id = Column(
        Integer,
        ForeignKey('nodes.id', ondelete='SET NULL'),
        nullable=True
    )
    node_role = Column(String(consts.ROLE_NAME_MAX_SIZE), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.now)
    configuration = Column(MutableDict.as_mutable(JSON), nullable=False,
                           default={}, server_default='{}')
