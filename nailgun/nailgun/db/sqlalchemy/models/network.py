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
from sqlalchemy import String
from sqlalchemy import Unicode
from sqlalchemy.orm import relationship, backref

from nailgun.db.sqlalchemy.models.base import Base


class IPAddr(Base):
    __tablename__ = 'ip_addrs'
    id = Column(Integer, primary_key=True)
    network = Column(Integer, ForeignKey('networks.id', ondelete="CASCADE"))
    node = Column(Integer, ForeignKey('nodes.id', ondelete="CASCADE"))
    ip_addr = Column(String(25), nullable=False)

    network_data = relationship("Network")
    node_data = relationship("Node")


class IPAddrRange(Base):
    __tablename__ = 'ip_addr_ranges'
    id = Column(Integer, primary_key=True)
    network_group_id = Column(Integer, ForeignKey('network_groups.id'))
    first = Column(String(25), nullable=False)
    last = Column(String(25), nullable=False)


class Vlan(Base):
    __tablename__ = 'vlan'
    id = Column(Integer, primary_key=True)
    network = relationship("Network",
                           backref=backref("vlan"))


class Network(Base):
    __tablename__ = 'networks'
    id = Column(Integer, primary_key=True)
    # can be nullable only for fuelweb admin net
    release = Column(Integer, ForeignKey('releases.id'))
    name = Column(Unicode(100), nullable=False)
    vlan_id = Column(Integer, ForeignKey('vlan.id'))
    network_group_id = Column(Integer, ForeignKey('network_groups.id'))
    cidr = Column(String(25), nullable=False)
    gateway = Column(String(25))
    nodes = relationship(
        "Node",
        secondary=IPAddr.__table__,
        backref="networks")


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
    networks = relationship("Network", cascade="delete",
                            backref="network_group")
    cidr = Column(String(25))
    gateway = Column(String(25))

    netmask = Column(String(25), nullable=False)
    ip_ranges = relationship(
        "IPAddrRange",
        backref="network_group"
    )

    @classmethod
    def generate_vlan_ids_list(cls, ng):
        if ng["vlan_start"] is None:
            return []
        vlans = [
            i for i in xrange(
                int(ng["vlan_start"]),
                int(ng["vlan_start"]) + int(ng["amount"])
            )
        ]
        return vlans

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
