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

from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.base import list_attrs


class IPAddr(Base):
    __tablename__ = 'ip_addrs'
    id = Column(Integer, primary_key=True)
    network = Column(Integer, ForeignKey('network_groups.id',
                                         ondelete="CASCADE"))
    node = Column(Integer, ForeignKey('nodes.id', ondelete="CASCADE"))
    ip_addr = Column(String(25), nullable=False)

    network_data = relationship("NetworkGroup")
    node_data = relationship("Node")

    def __repr__(self):
        return "IPAddr\n" + list_attrs(["id", "network", "node",
                                        "ip_addr", "network_data",
                                        "node_data"], self).__str__()

class IPAddrRange(Base):
    __tablename__ = 'ip_addr_ranges'
    id = Column(Integer, primary_key=True)
    network_group_id = Column(Integer, ForeignKey('network_groups.id'))
    first = Column(String(25), nullable=False)
    last = Column(String(25), nullable=False)

    def __repr__(self):
        return "IPAddrRange\n" + list_attrs(["id", "network_group_id",
                                             "first", "last"], self).__str__()


class NetworkGroup(Base):
    __tablename__ = 'network_groups'
    NAMES = (
        # Node networks
        'fuelweb_admin',
        'storage',
        # internal in terms of fuel
        'management',
        'public',

        # VM networks
        'floating',
        # private in terms of fuel
        'fixed',
        'private'
    )

    id = Column(Integer, primary_key=True)
    name = Column(Enum(*NAMES, name='network_group_name'), nullable=False)
    # can be nullable only for fuelweb admin net
    release = Column(Integer, ForeignKey('releases.id'))
    # can be nullable only for fuelweb admin net
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    network_size = Column(Integer, default=256)
    amount = Column(Integer, default=1)
    vlan_start = Column(Integer)
    cidr = Column(String(25))
    gateway = Column(String(25))
    netmask = Column(String(25), nullable=False)
    ip_ranges = relationship(
        "IPAddrRange",
        backref="network_group",
        cascade="all, delete"
    )
    nodes = relationship(
        "Node",
        secondary=IPAddr.__table__,
        backref="networks")

    @property
    def meta(self):
        if self.cluster:
            meta = self.cluster.release.networks_metadata[
                self.cluster.net_provider
            ]["networks"]
            for net in meta:
                if net["name"] == self.name:
                    return net
        return {}

    def __repr__(self):
        return "NetworkGroup\n" + list_attrs(["id", "name",
                                              "release", "cluster_id",
                                              "network_size", "amount",
                                              "vlan_start", "cidr", "gateway",
                                              "netmask"], self).__str__()

class AllowedNetworks(Base):
    __tablename__ = 'allowed_networks'
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

    def __repr__(self):
        return "AllowedNetworks\n" + list_attrs(["id", "network_id",
                                                 "interface_id"],
                                                self).__str__()

class NetworkAssignment(Base):
    __tablename__ = 'net_assignments'
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

    def __repr__(self):
        return "NetworkAssignment\n" + list_attrs(["id", "network_id",
                                                   "interface_id"],
                                                  self).__str__()
