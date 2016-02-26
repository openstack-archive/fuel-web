#    Copyright 2014 Mirantis, Inc.
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
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import relationship

from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.mutable import MutableList


class ClusterPlugin(Base):

    __tablename__ = 'cluster_plugins'

    id = Column(Integer, primary_key=True)
    plugin_id = Column(Integer,
                       ForeignKey('plugins.id', ondelete='CASCADE'),
                       nullable=False)
    cluster_id = Column(Integer,
                        ForeignKey('clusters.id', ondelete='CASCADE'),
                        nullable=False)
    enabled = Column(Boolean,
                     nullable=False,
                     default=False,
                     server_default='false')
    # Initially, 'attributes' is a copy of 'Plugin.attributes_metadata'.
    # We need this column in order to store in there the modified (by user)
    # version of attributes, because we don't want to store them in cluster
    # attributes with no chance to remove.
    attributes = Column(MutableDict.as_mutable(JSON),
                        nullable=False,
                        server_default='{}')


class NodeNICInterfaceClusterPlugin(Base):

    __tablename__ = 'node_nic_interface_cluster_plugins'
    id = Column(Integer, primary_key=True)
    cluster_plugin_id = Column(
        Integer,
        ForeignKey('cluster_plugins.id', ondelete='CASCADE'),
        nullable=False)
    interface_id = Column(
        Integer,
        ForeignKey('node_nic_interfaces.id', ondelete='CASCADE'),
        nullable=False)
    node_id = Column(
        Integer,
        ForeignKey('nodes.id', ondelete='CASCADE'),
        nullable=False)
    attributes = Column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        server_default='{}')


class NodeBondInterfaceClusterPlugin(Base):

    __tablename__ = 'node_bond_interface_cluster_plugins'
    id = Column(Integer, primary_key=True)
    cluster_plugin_id = Column(
        Integer,
        ForeignKey('cluster_plugins.id', ondelete='CASCADE'),
        nullable=False)
    bond_id = Column(
        Integer,
        ForeignKey('node_bond_interfaces.id', ondelete='CASCADE'),
        nullable=False)
    node_id = Column(
        Integer,
        ForeignKey('nodes.id', ondelete='CASCADE'),
        nullable=False)
    attributes = Column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        server_default='{}')


class NodeClusterPlugin(Base):

    __tablename__ = 'node_cluster_plugins'
    id = Column(Integer, primary_key=True)
    cluster_plugin_id = Column(
        Integer,
        ForeignKey('cluster_plugins.id', ondelete='CASCADE'),
        nullable=False)
    node_id = Column(
        Integer,
        ForeignKey('nodes.id', ondelete='CASCADE'),
        nullable=False)
    attributes = Column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        server_default='{}')


class Plugin(Base):

    __tablename__ = 'plugins'

    __table_args__ = (
        UniqueConstraint('name', 'version', name='_name_version_unique'),)

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    title = Column(String(100), nullable=False)
    version = Column(String(32), nullable=False)
    description = Column(String(400))
    releases = Column(MutableList.as_mutable(JSON), default=[])
    fuel_version = Column(MutableList.as_mutable(JSON), default=[])
    groups = Column(
        MutableList.as_mutable(JSON), server_default='[]', nullable=False)
    authors = Column(
        MutableList.as_mutable(JSON), server_default='[]', nullable=False)
    licenses = Column(
        MutableList.as_mutable(JSON), server_default='[]', nullable=False)
    homepage = Column(Text, nullable=True)
    package_version = Column(String(32), nullable=False)
    is_hotpluggable = Column(Boolean, default=False)
    attributes_metadata = Column(
        MutableDict.as_mutable(JSON), server_default='{}', nullable=False)
    volumes_metadata = Column(
        MutableDict.as_mutable(JSON), server_default='{}', nullable=False)
    roles_metadata = Column(
        MutableDict.as_mutable(JSON), server_default='{}', nullable=False)
    network_roles_metadata = Column(
        MutableList.as_mutable(JSON), server_default='[]', nullable=False)
    nic_attributes_metadata = Column(
        MutableDict.as_mutable(JSON), server_default='{}', nullable=False)
    bond_attributes_metadata = Column(
        MutableDict.as_mutable(JSON), server_default='{}', nullable=False)
    node_attributes_metadata = Column(
        MutableDict.as_mutable(JSON), server_default='{}', nullable=False)
    components_metadata = Column(
        MutableList.as_mutable(JSON), server_default='[]')
    # TODO(apopovych): To support old plugins versions we need separate
    # tasks which runs directly during deployment(stored in `deployment_tasks`
    # attribute) and which executes before/after of deployment process
    # (also called pre/post deployment tasks and stored in `tasks`
    # attribute). In future `deployment_tasks` and `tasks` should have
    # one format and this attribute will be removed.
    # Will be deprecated since plugins v5

    # (ikutukov) tasks yaml will stay here till fuel EOL to support upgrades
    # with old environments and old plugins.
    tasks = Column(
        MutableList.as_mutable(JSON), server_default='[]', nullable=False)
    deployment_graphs = relationship(
        "PluginDeploymentGraph",
        back_populates="plugin",
        lazy="dynamic")
    clusters = relationship("Cluster",
                            secondary=ClusterPlugin.__table__,
                            backref="plugins")
    links = relationship(
        "PluginLink", backref="plugin", cascade="delete")
