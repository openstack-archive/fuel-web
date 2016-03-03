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

import sqlalchemy as sa

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.mutable import MutableDict
from nailgun.db.sqlalchemy.models.mutable import MutableList


class DeploymentGraph(Base):
    __tablename__ = 'deployment_graphs'
    id = sa.Column(
        sa.Integer,
        primary_key=True)
    verbose_name = sa.Column(
        # not planned to used in business logic and
        # added to make work with custom graphs convenient
        sa.String(255),
        nullable=True)
    tasks = sa.orm.relationship(
        'DeploymentGraphTask',
        back_populates="deployment_graph")

    plugins = sa.orm.relationship(
        "PluginDeploymentGraph",
        back_populates="deployment_graph",
        lazy="dynamic")
    clusters = sa.orm.relationship(
        "ClusterDeploymentGraph",
        back_populates="deployment_graph",
        lazy="dynamic")
    releases = sa.orm.relationship(
        "ReleaseDeploymentGraph",
        back_populates="deployment_graph",
        lazy="dynamic")


class DeploymentGraphTask(Base):
    __tablename__ = 'deployment_graph_tasks'
    __table_args__ = (
        sa.UniqueConstraint(
            'deployment_graph_id',
            'task_name',
            name='_task_name_deployment_graph_id_uc'),
    )
    id = sa.Column(
        sa.Integer,
        primary_key=True)
    deployment_graph_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('deployment_graphs.id', ondelete='CASCADE'),
        nullable=False)
    deployment_graph = sa.orm.relationship(
        'DeploymentGraph',
        back_populates='tasks')

    # not task_id because it could be perceived as fk
    # and not id because it is not unique inside table
    task_name = sa.Column(
        sa.String(255),
        index=True,
        nullable=False)
    version = sa.Column(
        sa.String(255),
        nullable=False,
        server_default='1.0.0',
        default='1.0.0')
    condition = sa.Column(
        sa.Text,
        nullable=True)
    type = sa.Column(
        sa.Enum(
            *consts.ORCHESTRATOR_TASK_TYPES,
            name='deployment_graph_tasks_type'),
        nullable=False)
    groups = sa.Column(
        sa.dialects.postgresql.ARRAY(sa.String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    tasks = sa.Column(
        sa.dialects.postgresql.ARRAY(sa.String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    roles = sa.Column(    # node roles
        sa.dialects.postgresql.ARRAY(sa.String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    # list of Nailgun events on which this task should be re-executed
    reexecute_on = sa.Column(
        sa.dialects.postgresql.ARRAY(sa.String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    refresh_on = sa.Column(    # new in 8.0
        sa.dialects.postgresql.ARRAY(sa.String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    required_for = sa.Column(
        sa.dialects.postgresql.ARRAY(sa.String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    requires = sa.Column(
        sa.dialects.postgresql.ARRAY(sa.String(255)),
        default=[],
        server_default='{}',
        nullable=False)
    # cross-depended-by with hypen is deprecated notation
    cross_depended_by = sa.Column(
        MutableList.as_mutable(JSON),
        default=[],
        server_default='[]')
    # cross-depends with hypen is deprecated notation
    cross_depends = sa.Column(
        MutableList.as_mutable(JSON),
        default=[],
        server_default='[]')
    parameters = sa.Column(
        MutableDict.as_mutable(JSON),
        default={},
        server_default='{}')
    # custom field for all fields that does not fit into the schema
    _custom = sa.Column(
        MutableDict.as_mutable(JSON),
        default={},
        server_default='{}')


class ReleaseDeploymentGraph(Base):
    __tablename__ = 'release_deployment_graphs'
    __table_args__ = (
        sa.UniqueConstraint(
            'release_id',
            'type',
            # deployment_graph_id is not under constraint
            name='_type_deployment_graph_id_uc'),
    )
    id = sa.Column(
        sa.Integer,
        primary_key=True)
    type = sa.Column(
        sa.String(255),
        nullable=False)
    deployment_graph_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('deployment_graphs.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    deployment_graph = sa.orm.relationship(
        "DeploymentGraph",
        back_populates="releases")
    release_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('releases.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    release = sa.orm.relationship(
        "Release",
        back_populates="deployment_graphs")


class PluginDeploymentGraph(Base):
    # For plugins v 5.0.0 multiple release configuration is possible
    # thus it will be possible to link graphs to plugin->releaseX
    # configuration record.
    # So far graphs is connected only to plugin record.
    __tablename__ = 'plugin_deployment_graphs'
    __table_args__ = (
        sa.UniqueConstraint(
            'plugin_id',
            'type',
            # deployment_graph_id is not under constraint
            name='_type_deployment_graph_id_uc'),
    )
    id = sa.Column(
        sa.Integer,
        primary_key=True)
    type = sa.Column(
        sa.String(255),
        nullable=False)
    deployment_graph_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('deployment_graphs.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    deployment_graph = sa.orm.relationship(
        "DeploymentGraph",
        back_populates="plugins")
    plugin_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('plugins.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    plugin = sa.orm.relationship(
        "Plugin",
        back_populates="deployment_graphs")


class ClusterDeploymentGraph(Base):
    __tablename__ = 'cluster_deployment_graphs'
    __table_args__ = (
        sa.UniqueConstraint(
            'cluster_id',
            'type',
            # deployment_graph_id is not under constraint
            name='_type_deployment_graph_id_uc'),
    )
    id = sa.Column(
        sa.Integer,
        primary_key=True)
    type = sa.Column(
        sa.String(255),
        nullable=False)
    deployment_graph_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('deployment_graphs.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    deployment_graph = sa.orm.relationship(
        "DeploymentGraph",
        back_populates="clusters")
    cluster_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('clusters.id', ondelete="CASCADE"),
        nullable=False,
        index=True)
    cluster = sa.orm.relationship(
        "Cluster",
        back_populates="deployment_graphs")
