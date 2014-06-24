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

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.fields import LowercaseString
from nailgun.db.sqlalchemy.models.network import NetworkBondAssignment
from nailgun.db.sqlalchemy.models.network import NetworkNICAssignment
from nailgun.logger import logger
from nailgun.volumes.manager import VolumeManager


class NodeRoles(Base):
    __tablename__ = 'node_roles'
    id = Column(Integer, primary_key=True)
    role = Column(Integer, ForeignKey('roles.id', ondelete="CASCADE"))
    node = Column(Integer, ForeignKey('nodes.id'))


class PendingNodeRoles(Base):
    __tablename__ = 'pending_node_roles'
    id = Column(Integer, primary_key=True)
    role = Column(Integer, ForeignKey('roles.id', ondelete="CASCADE"))
    node = Column(Integer, ForeignKey('nodes.id'))


class Role(Base):
    __tablename__ = 'roles'
    __table_args__ = (
        UniqueConstraint('name', 'release_id'),
    )
    id = Column(Integer, primary_key=True)
    release_id = Column(
        Integer,
        ForeignKey('releases.id', ondelete='CASCADE'),
        nullable=False
    )
    name = Column(String(50), nullable=False)


class Node(Base):
    __tablename__ = 'nodes'
    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), nullable=False,
                  default=lambda: str(uuid.uuid4()), unique=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    name = Column(Unicode(100))
    status = Column(
        Enum(*consts.NODE_STATUSES, name='node_status'),
        nullable=False,
        default=consts.NODE_STATUSES.discover
    )
    meta = Column(JSON, default={})
    mac = Column(LowercaseString(17), nullable=False, unique=True)
    ip = Column(String(15))
    fqdn = Column(String(255))
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
    role_list = relationship(
        "Role",
        secondary=NodeRoles.__table__,
        backref=backref("nodes", cascade="all,delete")
    )
    pending_role_list = relationship(
        "Role",
        secondary=PendingNodeRoles.__table__,
        backref=backref("pending_nodes", cascade="all,delete")
    )
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
        return VolumeManager(self)

    @property
    def needs_reprovision(self):
        return self.status == 'error' and self.error_type == 'provision' and \
            not self.pending_deletion

    @property
    def needs_redeploy(self):
        return (self.status == 'error' or len(self.pending_roles)) and \
            not self.pending_deletion

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
    def roles(self):
        return [role.name for role in self.role_list]

    @roles.setter
    def roles(self, new_roles):
        if not self.cluster:
            logger.warning(
                u"Attempting to assign roles to node "
                u"'{0}' which isn't added to cluster".format(
                    self.name or self.id
                )
            )
            return
        if new_roles:
            self.role_list = db().query(Role).filter_by(
                release_id=self.cluster.release_id,
            ).filter(
                Role.name.in_(new_roles)
            ).all()
        else:
            self.role_list = []

    @property
    def pending_roles(self):
        return [role.name for role in self.pending_role_list]

    @property
    def all_roles(self):
        """Returns all roles, self.roles and self.pending_roles."""
        return set(self.pending_roles + self.roles)

    @pending_roles.setter
    def pending_roles(self, new_roles):
        if not self.cluster:
            logger.warning(
                u"Attempting to assign pending_roles to node "
                u"'{0}' which isn't added to cluster".format(
                    self.name or self.id
                )
            )
            return
        self.pending_role_list = db().query(Role).filter_by(
            release_id=self.cluster.release_id,
        ).filter(
            Role.name.in_(new_roles)
        ).all()

    @property
    def admin_interface(self):
        """Iterate over interfaces, if admin subnet include
        ip address of current interface then return this interface.

        :raises: errors.CanNotFindInterface
        """
        # TODO(enchantner): move to object
        from nailgun.network.manager import NetworkManager
        return NetworkManager.get_admin_interface(self)

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

    def reset_name_to_default(self):
        """Reset name to default
        TODO(el): move to node REST object which
        will be introduced in 5.0 release
        """
        self.name = u'Untitled ({0})'.format(self.mac[-5:])


class NodeAttributes(Base):
    __tablename__ = 'node_attributes'
    id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey('nodes.id'))
    volumes = Column(JSON, default=[])
    interfaces = Column(JSON, default={})


class NodeNICInterface(Base):
    __tablename__ = 'node_nic_interfaces'
    id = Column(Integer, primary_key=True)
    node_id = Column(
        Integer,
        ForeignKey('nodes.id', ondelete="CASCADE"),
        nullable=False)
    name = Column(String(128), nullable=False)
    mac = Column(LowercaseString(17), nullable=False)
    max_speed = Column(Integer)
    current_speed = Column(Integer)
    assigned_networks_list = relationship(
        "NetworkGroup",
        secondary=NetworkNICAssignment.__table__,
        order_by="NetworkGroup.id")
    ip_addr = Column(String(25))
    netmask = Column(String(25))
    state = Column(String(25))
    parent_id = Column(Integer, ForeignKey('node_bond_interfaces.id'))

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


class NodeBondInterface(Base):
    __tablename__ = 'node_bond_interfaces'
    id = Column(Integer, primary_key=True)
    node_id = Column(
        Integer,
        ForeignKey('nodes.id', ondelete="CASCADE"),
        nullable=False)
    name = Column(String(32), nullable=False)
    mac = Column(LowercaseString(17))
    assigned_networks_list = relationship(
        "NetworkGroup",
        secondary=NetworkBondAssignment.__table__,
        order_by="NetworkGroup.id")
    state = Column(String(25))
    flags = Column(JSON, default={})
    mode = Column(
        Enum(
            *consts.OVS_BOND_MODES,
            name='bond_mode'
        ),
        nullable=False,
        default=consts.OVS_BOND_MODES[0]
    )
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
