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

from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import relationship

from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON


class ClusterPlugins(Base):

    __tablename__ = 'cluster_plugins'
    id = Column(Integer, primary_key=True)
    plugin_id = Column(Integer, ForeignKey('plugins.id', ondelete='CASCADE'),
                       nullable=False)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))


class Plugin(Base):

    __tablename__ = 'plugins'

    __table_args__ = (
        UniqueConstraint('name', 'version', name='_name_version_unique'),)

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    title = Column(String(100), nullable=False)
    version = Column(String(32), nullable=False)
    description = Column(String(400))
    releases = Column(JSON, default=[])
    fuel_version = Column(JSON, default=[])
    package_version = Column(String(32), nullable=False)
    clusters = relationship("Cluster",
                            secondary=ClusterPlugins.__table__,
                            backref="plugins")
