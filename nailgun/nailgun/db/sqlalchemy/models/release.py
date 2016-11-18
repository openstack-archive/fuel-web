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

from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Unicode
from sqlalchemy import UniqueConstraint

from sqlalchemy.dialects import postgresql as psql
from sqlalchemy.orm import relationship

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.mutable import MutableDict
from nailgun.db.sqlalchemy.models.mutable import MutableList
from nailgun.utils import get_environment_version


class Release(Base):
    __tablename__ = 'releases'
    __table_args__ = (
        UniqueConstraint('name', 'version'),
    )
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(100), nullable=False)
    version = Column(String(30), nullable=False)
    description = Column(Unicode)
    operating_system = Column(String(50), nullable=False)
    state = Column(
        Enum(
            *consts.RELEASE_STATES,
            name='release_state'
        ),
        nullable=False,
        default=consts.RELEASE_STATES.unavailable
    )
    networks_metadata = Column(MutableDict.as_mutable(JSON), default={})
    attributes_metadata = Column(MutableDict.as_mutable(JSON), default={})
    volumes_metadata = Column(MutableDict.as_mutable(JSON), default={})
    modes_metadata = Column(MutableDict.as_mutable(JSON), default={})
    roles_metadata = Column(MutableDict.as_mutable(JSON), default={})
    tags_metadata = Column(
        MutableDict.as_mutable(JSON), server_default='{}', nullable=False)
    network_roles_metadata = Column(
        MutableList.as_mutable(JSON), default=[], server_default='[]')
    vmware_attributes_metadata = Column(
        MutableDict.as_mutable(JSON), default={})
    components_metadata = Column(
        MutableList.as_mutable(JSON), default=[], server_default='[]')
    required_component_types = Column(MutableList.as_mutable(JSON), default=[],
                                      server_default='[]', nullable=False)
    modes = Column(MutableList.as_mutable(JSON), default=[])
    clusters = relationship(
        "Cluster",
        primaryjoin="Release.id==Cluster.release_id",
        backref="release",
        cascade="all,delete")
    extensions = Column(psql.ARRAY(String(consts.EXTENSION_NAME_MAX_SIZE)),
                        default=[], nullable=False, server_default='{}')
    node_attributes = Column(MutableDict.as_mutable(JSON), default={},
                             server_default='{}', nullable=False)
    nic_attributes = Column(MutableDict.as_mutable(JSON), default={},
                            server_default='{}', nullable=False)
    bond_attributes = Column(MutableDict.as_mutable(JSON), default={},
                             server_default='{}', nullable=False)

    # TODO(enchantner): get rid of properties

    @property
    def openstack_version(self):
        return self.version.split('-')[0]

    @property
    def environment_version(self):
        """Returns environment version based on release version.

        :returns: an environment version
        """
        return get_environment_version(self.version)

    @property
    def os_weight(self):
        try:
            weight = consts.RELEASE_OS[::-1].index(self.operating_system)
        except ValueError:
            weight = -1

        return weight

    def __cmp__(self, other):
        """Allows to compare two releases

        :other: an instance of nailgun.db.sqlalchemy.models.release.Release
        """
        if self.environment_version < other.environment_version:
            return -1
        if self.environment_version > other.environment_version:
            return 1

        if self.openstack_version < other.openstack_version:
            return -1
        if self.openstack_version > other.openstack_version:
            return 1

        if self.os_weight == other.os_weight == -1:
            if self.operating_system > other.operating_system:
                return -1
            if self.operating_system < other.operating_system:
                return 1
        else:
            if self.os_weight < other.os_weight:
                return -1
            if self.os_weight > other.os_weight:
                return 1

        return 0
