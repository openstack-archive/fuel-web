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

from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.orm import relationship

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.mutable import MutableDict
from nailgun.db.sqlalchemy.models.mutable import MutableList
from nailgun.logger import logger


class NodeGroup(Base):
    __tablename__ = 'nodegroups'
    __table_args__ = (
        UniqueConstraint('cluster_id', 'name',
                         name='_name_cluster_uc'),)
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id', ondelete='CASCADE'))
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
    cluster_id = Column(Integer, ForeignKey('clusters.id', ondelete='CASCADE'))
    group_id = Column(
        Integer,
        ForeignKey('nodegroups.id', ondelete='SET NULL'),
        nullable=True
    )
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
    error_type = Column(String(100))
    error_msg = Column(Text)
    timestamp = Column(DateTime, nullable=False)
    online = Column(Boolean, default=True)
    labels = Column(
        MutableDict.as_mutable(JSON), nullable=False, server_default='{}')
    roles = Column(psql.ARRAY(String(consts.ROLE_NAME_MAX_SIZE)),
                   default=[], nullable=False, server_default='{}')
    pending_roles = Column(psql.ARRAY(String(consts.ROLE_NAME_MAX_SIZE)),
                           default=[], nullable=False, server_default='{}')
    primary_tags = Column(
        MutableList.as_mutable(psql.ARRAY(String(consts.ROLE_NAME_MAX_SIZE))),
        default=[], nullable=False, server_default='{}')

    nic_interfaces = relationship("NodeNICInterface", backref="node",
                                  cascade="all, delete-orphan",
                                  order_by="NodeNICInterface.name")
    bond_interfaces = relationship("NodeBondInterface", backref="node",
                                   cascade="all, delete-orphan",
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
    vms_conf = Column(MutableList.as_mutable(JSON),
                      default=[], server_default='[]', nullable=False)
    attributes = Column(
        MutableDict.as_mutable(JSON),
        default={}, server_default='{}', nullable=False)

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
        from nailgun.extensions.network_manager.manager import NetworkManager
        return NetworkManager.get_node_networks(self)

    @property
    def needs_reprovision(self):
        return self.status == 'error' and self.error_type == 'provision' and \
            not self.pending_deletion

    @property
    def needs_redeploy(self):
        return (
            self.status in [
                consts.NODE_STATUSES.error,
                consts.NODE_STATUSES.provisioned,
                consts.NODE_STATUSES.stopped
            ] or len(self.pending_roles)) and not self.pending_deletion

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
