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

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import Unicode

from sqlalchemy.orm import backref
from sqlalchemy.orm import relationship

from nailgun import consts

from nailgun.db import db
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.node import Node


class ClusterChanges(Base):
    __tablename__ = 'cluster_changes'
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    node_id = Column(Integer, ForeignKey('nodes.id', ondelete='CASCADE'))
    name = Column(
        Enum(*consts.CLUSTER_CHANGES, name='possible_changes'),
        nullable=False
    )


class Cluster(Base):
    __tablename__ = 'clusters'
    id = Column(Integer, primary_key=True)
    mode = Column(
        Enum(*consts.CLUSTER_MODES, name='cluster_mode'),
        nullable=False,
        default=consts.CLUSTER_MODES.ha_compact
    )
    status = Column(
        Enum(*consts.CLUSTER_STATUSES, name='cluster_status'),
        nullable=False,
        default=consts.CLUSTER_STATUSES.new
    )
    net_provider = Column(
        Enum(*consts.CLUSTER_NET_PROVIDERS, name='net_provider'),
        nullable=False,
        default=consts.CLUSTER_NET_PROVIDERS.nova_network
    )
    network_config = relationship("NetworkingConfig",
                                  backref=backref("cluster"),
                                  cascade="all,delete",
                                  uselist=False)
    grouping = Column(
        Enum(*consts.CLUSTER_GROUPING, name='cluster_grouping'),
        nullable=False,
        default=consts.CLUSTER_GROUPING.roles
    )
    name = Column(Unicode(50), unique=True, nullable=False)
    release_id = Column(Integer, ForeignKey('releases.id'), nullable=False)
    pending_release_id = Column(Integer, ForeignKey('releases.id'))
    nodes = relationship(
        "Node", backref="cluster", cascade="delete", order_by='Node.id')
    tasks = relationship("Task", backref="cluster", cascade="delete")
    attributes = relationship("Attributes", uselist=False,
                              backref="cluster", cascade="delete")
    changes_list = relationship("ClusterChanges", backref="cluster",
                                cascade="delete")
    # We must keep all notifications even if cluster is removed.
    # It is because we want user to be able to see
    # the notification history so that is why we don't use
    # cascade="delete" in this relationship
    # During cluster deletion sqlalchemy engine will set null
    # into cluster foreign key column of notification entity
    notifications = relationship("Notification", backref="cluster")
    network_groups = relationship(
        "NetworkGroup",
        backref="cluster",
        cascade="delete",
        order_by="NetworkGroup.id"
    )
    replaced_deployment_info = Column(JSON, default={})
    replaced_provisioning_info = Column(JSON, default={})
    is_customized = Column(Boolean, default=False)
    fuel_version = Column(Text, nullable=False)

    @property
    def changes(self):
        return [
            {"name": i.name, "node_id": i.node_id}
            for i in self.changes_list
        ]

    @changes.setter
    def changes(self, value):
        self.changes_list = value

    @property
    def is_ha_mode(self):
        return self.mode in ('ha_full', 'ha_compact')

    @property
    def full_name(self):
        return '%s (id=%s, mode=%s)' % (self.name, self.id, self.mode)

    @property
    def is_locked(self):
        if self.status in ("new", "stopped") and not \
                db().query(Node).filter_by(
                    cluster_id=self.id,
                    status="ready"
                ).count():
            return False
        return True


class Attributes(Base):
    __tablename__ = 'attributes'
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    editable = Column(JSON)
    generated = Column(JSON)
