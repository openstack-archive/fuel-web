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

from nailgun.api.models.base import Base
from nailgun.db import db


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


class NetworkConfiguration(object):
    @classmethod
    def update(cls, cluster, network_configuration):
        from nailgun.network.manager import NetworkManager
        network_manager = NetworkManager()

        if 'net_manager' in network_configuration:
            setattr(
                cluster,
                'net_manager',
                network_configuration['net_manager']
            )

        if 'dns_nameservers' in network_configuration:
            setattr(
                cluster,
                'dns_nameservers',
                network_configuration['dns_nameservers']['nameservers']
            )

        if 'networks' in network_configuration:
            for ng in network_configuration['networks']:
                if ng['id'] == network_manager.get_admin_network_group_id():
                    continue

                ng_db = db().query(NetworkGroup).get(ng['id'])

                for key, value in ng.iteritems():
                    if key == "ip_ranges":
                        cls._set_ip_ranges(ng['id'], value)
                    else:
                        if key == 'cidr' and \
                                not ng['name'] in ('public', 'floating'):
                            network_manager.update_range_mask_from_cidr(
                                ng_db, value)

                        setattr(ng_db, key, value)

                network_manager.create_networks(ng_db)
                ng_db.cluster.add_pending_changes('networks')

    @classmethod
    def _set_ip_ranges(cls, network_group_id, ip_ranges):
        # deleting old ip ranges
        db().query(IPAddrRange).filter_by(
            network_group_id=network_group_id).delete()

        for r in ip_ranges:
            new_ip_range = IPAddrRange(
                first=r[0],
                last=r[1],
                network_group_id=network_group_id)
            db().add(new_ip_range)
        db().commit()


class L2Topology(Base):
    __tablename__ = 'l2_topologies'
    id = Column(Integer, primary_key=True)
    network_id = Column(
        Integer,
        ForeignKey('network_groups.id', ondelete="CASCADE"),
        nullable=False
    )


class L2Connection(Base):
    __tablename__ = 'l2_connections'
    id = Column(Integer, primary_key=True)
    topology_id = Column(
        Integer,
        ForeignKey('l2_topologies.id', ondelete="CASCADE"),
        nullable=False
    )
    interface_id = Column(
        Integer,
        # If interface is removed we should somehow remove
        # all L2Topologes which include this interface.
        ForeignKey('node_nic_interfaces.id', ondelete="CASCADE"),
        nullable=False
    )


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
