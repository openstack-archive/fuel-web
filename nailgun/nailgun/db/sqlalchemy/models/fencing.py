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

from collections import namedtuple

from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer

from sqlalchemy.orm import backref
from sqlalchemy.orm import relationship

from nailgun.db import db
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON


enum = lambda *values: namedtuple('Enum', values)(*values)

FENCING_POLICIES = enum(
    'disabled',
    'poweroff',
    'reboot'
)

FENCING_PRIM_NAMES = enum(
    'ipmilan',
    'ilo',
    'drac5',
    'virsh',
    'apc',
    'apc_snmp'
)


class FencingConfiguration(Base):
    __tablename__ = 'fencing_configurations'

    id = Column(
        Integer,
        primary_key=True
    )
    cluster_id = Column(
        Integer,
        ForeignKey('clusters.id', ondelete="CASCADE")
    )
    cluster = relationship(
        "Cluster",
        backref=backref("fencing_config", uselist=False)
    )
    policy = Column(
        Enum(*FENCING_POLICIES, name='policy'),
        nullable=False,
        default=FENCING_POLICIES.disabled
    )
    primitives = relationship(
        "FencingPrimitive",
        backref="fencing_configuration",
        cascade="delete",
        order_by="FencingPrimitive.id"
    )


class FencingPrimitive(Base):
    __tablename__ = 'fencing_primitives'

    id = Column(
        Integer,
        primary_key=True
    )
    name = Column(
        Enum(*FENCING_PRIM_NAMES, name='name'),
        nullable=False
    )
    index = Column(
        Integer,
        nullable=True
    )
    configuration_id = Column(
        Integer,
        ForeignKey('fencing_configurations.id', ondelete="CASCADE")
    )
    node_id = Column(
        Integer,
        ForeignKey('nodes.id', ondelete="CASCADE")
    )
    parameters = Column(
        JSON,
        default={}
    )
