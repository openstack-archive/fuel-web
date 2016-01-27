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
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UnicodeText

from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.orm import backref
from sqlalchemy.orm import relationship

from oslo_serialization import jsonutils

from nailgun import consts

from nailgun.db import db
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.mutable import MutableList
from nailgun.db.sqlalchemy.models.node import Node


class ClusterChanges(Base):
    __tablename__ = 'cluster_changes'
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id', ondelete='CASCADE'))
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
        default=consts.CLUSTER_NET_PROVIDERS.neutron
    )
    network_config = relationship("NetworkingConfig",
                                  backref=backref("cluster"),
                                  cascade="all,delete",
                                  uselist=False)
    ui_settings = Column(
        JSON,
        nullable=False,
        server_default=jsonutils.dumps({
            "view_mode": "standard",
            "filter": {},
            "sort": [{"roles": "asc"}],
            "filter_by_labels": {},
            "sort_by_labels": [],
            "search": "",
            "show_all_node_groups": False
        }),
    )
    name = Column(UnicodeText, unique=True, nullable=False)
    release_id = Column(Integer, ForeignKey('releases.id'), nullable=False)
    pending_release_id = Column(Integer, ForeignKey('releases.id'))
    nodes = relationship(
        "Node", backref="cluster", cascade="delete", order_by='Node.id')
    tasks = relationship("Task", backref="cluster", cascade="delete")
    plugin_links = relationship(
        "ClusterPluginLink", backref="cluster", cascade="delete")
    attributes = relationship("Attributes", uselist=False,
                              backref="cluster", cascade="delete")
    changes_list = relationship("ClusterChanges", backref="cluster",
                                cascade="delete")
    vmware_attributes = relationship("VmwareAttributes", uselist=False,
                                     backref="cluster", cascade="delete")
    # We must keep all notifications even if cluster is removed.
    # It is because we want user to be able to see
    # the notification history so that is why we don't use
    # cascade="delete" in this relationship
    # During cluster deletion sqlalchemy engine will set null
    # into cluster foreign key column of notification entity
    notifications = relationship("Notification", backref="cluster")
    node_groups = relationship(
        "NodeGroup",
        backref="cluster",
        cascade="delete"
    )
    replaced_deployment_info = Column(JSON, default={})
    replaced_provisioning_info = Column(JSON, default={})
    is_customized = Column(Boolean, default=False)
    fuel_version = Column(Text, nullable=False)
    deployment_tasks = Column(JSON, default=[])
    components = Column(
        MutableList.as_mutable(JSON),
        default=[],
        server_default='[]',
        nullable=False)
    extensions = Column(psql.ARRAY(String(consts.EXTENSION_NAME_MAX_SIZE)),
                        default=[], nullable=False, server_default='{}')

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
        allowed_status = (
            consts.CLUSTER_STATUSES.new, consts.CLUSTER_STATUSES.stopped
        )
        return self.status not in allowed_status or bool(db().query(
            db().query(Node).filter_by(
                cluster_id=self.id,
                status=consts.NODE_STATUSES.ready
            ).exists()
        ).scalar())

    @property
    def network_groups(self):
        net_list = []
        for ng in self.node_groups:
            net_list.extend(ng.networks)
        return net_list


class Attributes(Base):
    __tablename__ = 'attributes'
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id', ondelete='CASCADE'))
    editable = Column(JSON)
    generated = Column(JSON)


class VmwareAttributes(Base):
    __tablename__ = 'vmware_attributes'
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id', ondelete='CASCADE'))
    editable = Column(JSON)
