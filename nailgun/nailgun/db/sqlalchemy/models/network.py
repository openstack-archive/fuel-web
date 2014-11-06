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
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy.orm import relationship
from sqlalchemy import String

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON


class IPAddr(Base):
    __tablename__ = 'ip_addrs'
    id = Column(Integer, primary_key=True)
    network = Column(Integer, ForeignKey('network_groups.id',
                                         ondelete="CASCADE"))
    node = Column(Integer, ForeignKey('nodes.id', ondelete="CASCADE"))
    ip_addr = Column(String(25), nullable=False)

    network_data = relationship("NetworkGroup")
    node_data = relationship("Node")


class IPAddrRange(Base):
    __tablename__ = 'ip_addr_ranges'
    id = Column(Integer, primary_key=True)
    network_group_id = Column(Integer, ForeignKey('network_groups.id'))
    first = Column(String(25), nullable=False)
    last = Column(String(25), nullable=False)


class NetworkGroup(Base):
    __tablename__ = 'network_groups'

    id = Column(Integer, primary_key=True)
    name = Column(Enum(*consts.NETWORKS, name='network_group_name'),
                  nullable=False)
    # can be nullable only for fuelweb admin net
    release = Column(Integer, ForeignKey('releases.id'))
    # can be nullable only for fuelweb admin net
    group_id = Column(Integer, ForeignKey('nodegroups.id'), nullable=True)
    vlan_start = Column(Integer)
    cidr = Column(String(25))
    gateway = Column(String(25))
    ip_ranges = relationship(
        "IPAddrRange",
        backref="network_group",
        cascade="all, delete"
    )
    nodes = relationship(
        "Node",
        secondary=IPAddr.__table__,
        backref="networks")
    meta = Column(JSON, default={})


class NetworkNICAssignment(Base):
    __tablename__ = 'net_nic_assignments'
    id = Column(Integer, primary_key=True)
    network_id = Column(
        Integer,
        ForeignKey('network_groups.id', ondelete="CASCADE"),
        nullable=False
    )
    interface_id = Column(
        Integer,
        ForeignKey('node_nic_interfaces.id', ondelete="CASCADE"),
        nullable=False
    )


class NetworkBondAssignment(Base):
    __tablename__ = 'net_bond_assignments'
    id = Column(Integer, primary_key=True)
    network_id = Column(
        Integer,
        ForeignKey('network_groups.id', ondelete="CASCADE"),
        nullable=False
    )
    bond_id = Column(
        Integer,
        ForeignKey('node_bond_interfaces.id', ondelete="CASCADE"),
        nullable=False
    )
