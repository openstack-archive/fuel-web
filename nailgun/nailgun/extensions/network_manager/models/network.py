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
import copy

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy.orm import relationship
from sqlalchemy import String
from sqlalchemy import Text

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.mutable import MutableDict
from nailgun.db.sqlalchemy.models.mutable import MutableList


class IPAddr(Base):
    __tablename__ = 'ip_addrs'
    id = Column(Integer, primary_key=True)
    network = Column(Integer, ForeignKey('network_groups.id',
                                         ondelete="CASCADE"))
    node = Column(Integer, ForeignKey('nodes.id', ondelete="CASCADE"))
    ip_addr = Column(psql.INET, nullable=False)
    vip_name = Column(String(50), nullable=True)
    vip_namespace = Column(
        String(50),
        nullable=True,
        server_default=None
    )
    is_user_defined = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false"
    )
    network_data = relationship("NetworkGroup")
    node_data = relationship("Node")


class IPAddrRange(Base):
    __tablename__ = 'ip_addr_ranges'
    id = Column(Integer, primary_key=True)
    network_group_id = Column(Integer, ForeignKey('network_groups.id',
                                                  ondelete="CASCADE"))
    first = Column(psql.INET, nullable=False)
    last = Column(psql.INET, nullable=False)


class NetworkGroup(Base):
    __tablename__ = 'network_groups'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    # can be nullable only for fuelweb admin net
    release = Column(Integer, ForeignKey('releases.id', ondelete='CASCADE'))
    # can be nullable only for fuelweb admin net
    group_id = Column(
        Integer,
        ForeignKey('nodegroups.id', ondelete='CASCADE'),
        nullable=True
    )
    vlan_start = Column(Integer)
    cidr = Column(psql.CIDR)
    gateway = Column(psql.INET)
    ip_ranges = relationship(
        "IPAddrRange",
        backref="network_group",
        cascade="all, delete, delete-orphan"
    )
    nodes = relationship(
        "Node",
        secondary=IPAddr.__table__,
        backref="networks",
        passive_deletes=True
    )
    meta = Column(MutableDict.as_mutable(JSON), default={})


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


class NodeNICInterface(Base):
    __tablename__ = 'node_nic_interfaces'
    id = Column(Integer, primary_key=True)
    node_id = Column(
        Integer,
        ForeignKey('nodes.id', ondelete="CASCADE"),
        nullable=False)
    name = Column(String(128), nullable=False)
    mac = Column(psql.MACADDR, nullable=False)
    max_speed = Column(Integer)
    current_speed = Column(Integer)
    assigned_networks_list = relationship(
        "NetworkGroup",
        secondary=NetworkNICAssignment.__table__,
        order_by="NetworkGroup.id")
    ip_addr = Column(psql.INET)
    netmask = Column(psql.INET)
    state = Column(String(25))
    interface_properties = Column(
        MutableDict.as_mutable(JSON), default={}, nullable=False,
        server_default='{}')
    parent_id = Column(
        Integer,
        ForeignKey('node_bond_interfaces.id', ondelete='SET NULL')
    )
    driver = Column(Text)
    bus_info = Column(Text)
    pxe = Column(Boolean, default=False, nullable=False)

    offloading_modes = Column(MutableList.as_mutable(JSON),
                              default=[], nullable=False,
                              server_default='[]')
    attributes = Column(
        MutableDict.as_mutable(JSON),
        default={}, server_default='{}', nullable=False)

    @property
    def type(self):
        return consts.NETWORK_INTERFACE_TYPES.ether

    @property
    def assigned_networks(self):
        return [
            {"id": n.id, "name": n.name}
            for n in self.assigned_networks_list
        ]

    @assigned_networks.setter
    def assigned_networks(self, value):
        self.assigned_networks_list = value

    # TODO(fzhadaev): move to object
    @classmethod
    def offloading_modes_as_flat_dict(cls, modes):
        """Represents multilevel structure of offloading modes as flat dict

        This is done to ease merging
        :param modes: list of offloading modes
        :return: flat dictionary {mode['name']: mode['state']}
        """
        result = dict()
        if modes is None:
            return result
        for mode in modes:
            result[mode["name"]] = mode["state"]
            if mode["sub"]:
                result.update(cls.offloading_modes_as_flat_dict(mode["sub"]))
        return result


class NodeBondInterface(Base):
    __tablename__ = 'node_bond_interfaces'
    id = Column(Integer, primary_key=True)
    node_id = Column(
        Integer,
        ForeignKey('nodes.id', ondelete="CASCADE"),
        nullable=False)
    name = Column(String(32), nullable=False)
    mac = Column(psql.MACADDR)
    assigned_networks_list = relationship(
        "NetworkGroup",
        secondary=NetworkBondAssignment.__table__,
        order_by="NetworkGroup.id")
    state = Column(String(25))
    interface_properties = Column(
        MutableDict.as_mutable(JSON), default={}, nullable=False,
        server_default='{}')
    mode = Column(
        Enum(
            *consts.BOND_MODES,
            name='bond_mode'
        ),
        nullable=False,
        default=consts.BOND_MODES.active_backup
    )
    bond_properties = Column(
        MutableDict.as_mutable(JSON), default={}, nullable=False,
        server_default='{}')
    slaves = relationship("NodeNICInterface", backref="bond")
    attributes = Column(
        MutableDict.as_mutable(JSON),
        default={}, server_default='{}', nullable=False)

    @property
    def max_speed(self):
        return None

    @property
    def current_speed(self):
        return None

    @property
    def type(self):
        return consts.NETWORK_INTERFACE_TYPES.bond

    @property
    def assigned_networks(self):
        return [
            {"id": n.id, "name": n.name}
            for n in self.assigned_networks_list
        ]

    @assigned_networks.setter
    def assigned_networks(self, value):
        self.assigned_networks_list = value

    @property
    def offloading_modes(self):
        tmp = None
        intersection_dict = {}
        for interface in self.slaves:
            modes = interface.offloading_modes
            if tmp is None:
                tmp = modes
                intersection_dict = \
                    interface.offloading_modes_as_flat_dict(tmp)
                continue
            intersection_dict = self._intersect_offloading_dicts(
                intersection_dict,
                interface.offloading_modes_as_flat_dict(modes)
            )

        return self._apply_intersection(tmp, intersection_dict)

    @offloading_modes.setter
    def offloading_modes(self, new_modes):
        new_modes_dict = \
            NodeNICInterface.offloading_modes_as_flat_dict(new_modes)
        for interface in self.slaves:
            self._update_modes(interface.offloading_modes, new_modes_dict)
            interface.offloading_modes.changed()

    def _update_modes(self, modes, update_dict):
        for mode in modes:
            if mode['name'] in update_dict:
                mode['state'] = update_dict[mode['name']]
            if mode['sub']:
                self._update_modes(mode['sub'], update_dict)

    def _intersect_offloading_dicts(self, dict1, dict2):
        result = dict()
        for mode in dict1:
            if mode in dict2:
                result[mode] = dict1[mode] and dict2[mode]
        return result

    def _apply_intersection(self, modes, intersection_dict):
        result = list()
        if modes is None:
            return result
        for mode in copy.deepcopy(modes):
            if mode["name"] not in intersection_dict:
                continue
            mode["state"] = intersection_dict[mode["name"]]
            if mode["sub"]:
                mode["sub"] = \
                    self._apply_intersection(mode["sub"], intersection_dict)
            result.append(mode)
        return result
