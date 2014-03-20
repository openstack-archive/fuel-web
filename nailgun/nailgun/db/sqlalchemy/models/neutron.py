# -*- coding: utf-8 -*-

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
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer

from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON


class NeutronConfig(Base):
    __tablename__ = 'neutron_configs'
    NET_SEGMENT_TYPES = ('vlan', 'gre')
    id = Column(Integer, primary_key=True)
    cluster_id = Column(
        Integer,
        ForeignKey('clusters.id', ondelete="CASCADE")
    )
    parameters = Column(JSON, default={})
    L2 = Column(JSON, default={})
    L3 = Column(JSON, default={})
    predefined_networks = Column(JSON, default={})

    segmentation_type = Column(
        Enum(*NET_SEGMENT_TYPES,
             name='segmentation_type'),
        nullable=False,
        default='vlan'
    )
