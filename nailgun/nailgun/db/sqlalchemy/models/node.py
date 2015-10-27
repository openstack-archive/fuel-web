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
import uuid

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import Unicode
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.ext.mutable import MutableDict

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.mutable import MutableList
from nailgun.db.sqlalchemy.models.network import NetworkBondAssignment
from nailgun.db.sqlalchemy.models.network import NetworkNICAssignment
from nailgun.extensions.volume_manager.manager import VolumeManager
from nailgun.logger import logger


class NodeGroup(Base):
    __tablename__ = 'nodegroups'
    __table_args__ = (
        UniqueConstraint('cluster_id', 'name',
                         name='_name_cluster_uc'),)
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    name = Column(String(50), nullable=False)
    is_default = Column(Boolean, default=False, nullable=False,
                        server_default='false', index=True)
    nodes = relationship("Node", backref="nodegroup")
    networks = relationship(
        "NetworkGroup",
        backref="nodegroup",
        cascade="delete, delete-orphan"
    )


class Node(Base):
    __tablename__ = 'nodes'
    __table_args__ = (
        UniqueConstraint('cluster_id', 'hostname',
                         name='_hostname_cluster_uc'),
    )
    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), nullable=False,
                  default=lambda: str(uuid.uuid4()), unique=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    group_id = Column(Integer, ForeignKey('nodegroups.id'), nullable=True)
    name = Column(Unicode(100))
    status = Column(
        Enum(*consts.NODE_STATUSES, name='node_status'),
        nullable=False,
        default=consts.NODE_STATUSES.discover
    )
    meta = Column(MutableDict.as_mutable(JSON), default={})
    mac = Column(psql.MACADDR, nullable=False, unique=True)
    ip = Column(psql.INET)
    hostname = Column(String(255), nullable=False,
                      default="", server_default="")
    manufacturer = Column(Unicode(50))
    platform_name = Column(String(150))
    kernel_params = Column(Text)
    progress = Column(Integer, default=0)
    os_platform = Column(String(150))
    pending_addition = Column(Boolean, default=False)
    pending_deletion = Column(Boolean, default=False)
    changes = relationship("ClusterChanges", backref="node")
    error_type = Column(Enum(*consts.NODE_ERRORS, name='node_error_type'))
    error_msg = Column(String(255))
    timestamp = Column(DateTime, nullable=False)
    online = Column(Boolean, default=True)
    labels = Column(
        MutableDict.as_mutable(JSON), nullable=False, server_default='{}')
    roles = Column(psql.ARRAY(String(consts.ROLE_NAME_MAX_SIZE)),
                   default=[], nullable=False, server_default='{}')
    pending_roles = Column(psql.ARRAY(String(consts.ROLE_NAME_MAX_SIZE)),
                           default=[], nullable=False, server_default='{}')
    primary_roles = Column(psql.ARRAY(String(consts.ROLE_NAME_MAX_SIZE)),
                           default=[], nullable=False, server_default='{}')
    attributes = relationship("NodeAttributes",
                              backref=backref("node"),
                              uselist=False,
                              cascade="all,delete")
    nic_interfaces = relationship("NodeNICInterface", backref="node",
                                  cascade="delete",
                                  order_by="NodeNICInterface.name")
    bond_interfaces = relationship("NodeBondInterface", backref="node",
                                   cascade="delete",
                                   order_by="NodeBondInterface.name")
    # hash function from raw node agent request data - for caching purposes
    agent_checksum = Column(String(40), nullable=True)

    ip_addrs = relationship("IPAddr", viewonly=True)
    replaced_deployment_info = Column(MutableList.as_mutable(JSON), default=[])
    replaced_provisioning_info = Column(
        MutableDict.as_mutable(JSON), default={})
    network_template = Column(MutableDict.as_mutable(JSON), default=None,
                              server_default=None, nullable=True)
    extensions = Column(psql.ARRAY(String(consts.EXTENSION_NAME_MAX_SIZE)),
                        default=[], nullable=False, server_default='{}')

    @property
    def interfaces(self):
        return self.nic_interfaces + self.bond_interfaces

    @property
    def uid(self):
        return str(self.id)

    @property
    def offline(self):
        return not self.online

    @property
    def network_data(self):
        # TODO(enchantner): move to object
        from nailgun.network.manager import NetworkManager
        return NetworkManager.get_node_networks(self)

    @property
    def volume_manager(self):
        # TODO(eli): will be moved into an extension.
        # Should be done as a part of blueprint:
        # https://blueprints.launchpad.net/fuel/+spec
        #                                 /volume-manager-refactoring
        return VolumeManager(self)

    @property
    def needs_reprovision(self):
        return self.status == 'error' and self.error_type == 'provision' and \
            not self.pending_deletion

    @property
    def needs_redeploy(self):
        return (
            self.status in ['error', 'provisioned'] or
            len(self.pending_roles)) and not self.pending_deletion

    @property
    def needs_redeletion(self):
        return self.status == 'error' and self.error_type == 'deletion'

    @property
    def human_readable_name(self):
        return self.name or self.mac

    @property
    def full_name(self):
        return u'%s (id=%s, mac=%s)' % (self.name, self.id, self.mac)

    @property
    def all_roles(self):
        """Returns all roles, self.roles and self.pending_roles."""
        return set(self.pending_roles + self.roles)

    def _check_interface_has_required_params(self, iface):
        return bool(iface.get('name') and iface.get('mac'))

    def _clean_iface(self, iface):
        # cleaning up unnecessary fields - set to None if bad
        for param in ["max_speed", "current_speed"]:
            val = iface.get(param)
            if not (isinstance(val, int) and val >= 0):
                val = None
            iface[param] = val
        return iface

    def update_meta(self, data):
        # helper for basic checking meta before updation
        result = []
        if "interfaces" in data:
            for iface in data["interfaces"]:
                if not self._check_interface_has_required_params(iface):
                    logger.warning(
                        "Invalid interface data: {0}. "
                        "Interfaces are not updated.".format(iface)
                    )
                    data["interfaces"] = self.meta.get("interfaces")
                    self.meta = data
                    return
                result.append(self._clean_iface(iface))

        data["interfaces"] = result
        self.meta = data

    def create_meta(self, data):
        # helper for basic checking meta before creation
        result = []
        if "interfaces" in data:
            for iface in data["interfaces"]:
                if not self._check_interface_has_required_params(iface):
                    logger.warning(
                        "Invalid interface data: {0}. "
                        "Skipping interface.".format(iface)
                    )
                    continue
                result.append(self._clean_iface(iface))

        data["interfaces"] = result
        self.meta = data


class NodeAttributes(Base):
    __tablename__ = 'node_attributes'
    id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey('nodes.id', ondelete='CASCADE'))
    interfaces = Column(MutableDict.as_mutable(JSON), default={})
    vms_conf = Column(MutableList.as_mutable(JSON),
                      default=[], server_default='[]')


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
        Integer, ForeignKey('node_bond_interfaces.id', ondelete='SET NULL'))
    driver = Column(Text)
    bus_info = Column(Text)
    pxe = Column(Boolean, default=False, nullable=False)

    offloading_modes = Column(MutableList.as_mutable(JSON),
                              default=[], nullable=False,
                              server_default='[]')

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
