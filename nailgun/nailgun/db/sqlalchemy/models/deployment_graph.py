#    Copyright 2016 Mirantis, Inc.
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
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy.orm import relationship
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.mutable import MutableDict
from nailgun.db.sqlalchemy.models.mutable import MutableList


class DeploymentGraph(Base):
    __tablename__ = 'deployment_graphs'
    id = Column(
        Integer,
        primary_key=True)
    verbose_name = Column(
        # not planned to used in business logic and
        # added to make work with custom graphs convenient
        String(255),
        nullable=True)
    tasks = relationship(
        'DeploymentGraphTask',
        back_populates="deployment_graph")

    plugins = relationship(
        "PluginDeploymentGraph",
        back_populates="deployment_graph",
        lazy="dynamic")
    clusters = relationship(
        "ClusterDeploymentGraph",
        back_populates="deployment_graph",
        lazy="dynamic")
    releases = relationship(
        "ReleaseDeploymentGraph",
        back_populates="deployment_graph",
        lazy="dynamic")


class DeploymentGraphTask(Base):
    __tablename__ = 'deployment_graph_tasks'
    __table_args__ = (
        UniqueConstraint(
            'deployment_graph_id',
            'task_name',
            name='_task_name_deployment_graph_id_uc'),
    )
    id = Column(
        Integer,
        primary_key=True)
    deployment_graph_id = Column(
        Integer,
        ForeignKey('deployment_graphs.id', ondelete='CASCADE'),
        nullable=False)
    deployment_graph = relationship('DeploymentGraph', back_populates="tasks")

    # not task_id because it could be perceived as fk
    # and not id because it is not unique inside table
    task_name = Column(
        String(255),
        index=True,
        nullable=False)
    version = Column(
        String(255),
        nullable=False,
        server_default='1.0.0',
        default='1.0.0')
    condition = Column(
        Text,
        nullable=True)
    type = Column(
        Enum(
            *consts.ORCHESTRATOR_TASK_TYPES,
            name='deployment_graph_tasks_type'),
        nullable=False)
    groups = Column(
        psql.ARRAY(String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    tasks = Column(
        psql.ARRAY(String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    roles = Column(    # node roles
        psql.ARRAY(String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    # list of Nailgun events on which this task should be re-executed
    reexecute_on = Column(
        psql.ARRAY(String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    refresh_on = Column(    # new in 8.0
        psql.ARRAY(String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    required_for = Column(
        psql.ARRAY(String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    requires = Column(
        psql.ARRAY(String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    # cross-depended-by with hypen is deprecated notation
    cross_depended_by = Column(
        MutableList.as_mutable(JSON),
        default=[],
        server_default='[]')
    # cross-depends with hypen is deprecated notation
    cross_depends = Column(
        MutableList.as_mutable(JSON),
        default=[],
        server_default='[]')
    parameters = Column(
        MutableDict.as_mutable(JSON),
        default={},
        server_default='{}')
    # custom field for all fields that does not fit into the schema
    _custom = Column(
        MutableDict.as_mutable(JSON),
        default={},
        server_default='{}')


class ReleaseDeploymentGraph(Base):
    __tablename__ = 'release_deployment_graphs'
    __table_args__ = (
        UniqueConstraint(
            'release_id',
            'type',
            # deployment_graph_id is not under constraint
            name='_type_deployment_graph_id_uc'),
    )
    id = Column(
        Integer,
        primary_key=True)
    type = Column(
        String(255),
        nullable=False)
    deployment_graph_id = Column(
        Integer,
        ForeignKey('deployment_graphs.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    deployment_graph = relationship(
        "DeploymentGraph",
        back_populates="releases")
    release_id = Column(
        Integer,
        ForeignKey('releases.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    release = relationship("Release", back_populates="deployment_graphs")


class PluginDeploymentGraph(Base):
    # For plugins v 5.0.0 multiple release configuration is possible
    # thus it will be possible to link graphs to plugin->releaseX
    # configuration record.
    # So far graphs is connected only to plugin record.
    __tablename__ = 'plugin_deployment_graphs'
    __table_args__ = (
        UniqueConstraint(
            'plugin_id',
            'type',
            # deployment_graph_id is not under constraint
            name='_type_deployment_graph_id_uc'),
    )
    id = Column(
        Integer,
        primary_key=True)
    type = Column(
        String(255),
        nullable=False)
    deployment_graph_id = Column(
        Integer,
        ForeignKey('deployment_graphs.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    deployment_graph = relationship(
        "DeploymentGraph",
        back_populates="plugins")
    plugin_id = Column(
        Integer,
        ForeignKey('plugins.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    plugin = relationship("Plugin", back_populates="deployment_graphs")


class ClusterDeploymentGraph(Base):
    __tablename__ = 'cluster_deployment_graphs'
    __table_args__ = (
        UniqueConstraint(
            'cluster_id',
            'type',
            # deployment_graph_id is not under constraint
            name='_type_deployment_graph_id_uc'),
    )
    id = Column(
        Integer,
        primary_key=True)
    type = Column(
        String(255),
        nullable=False)
    deployment_graph_id = Column(
        Integer,
        ForeignKey('deployment_graphs.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    deployment_graph = relationship(
        "DeploymentGraph",
        back_populates="clusters")
    cluster_id = Column(
        Integer,
        ForeignKey('clusters.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    cluster = relationship("Cluster", back_populates="deployment_graphs")
