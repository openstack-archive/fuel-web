# -*- coding: utf-8 -*-

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
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String

from nailgun import consts
from nailgun.db.sqlalchemy.models.base import Base
from nailgun.db.sqlalchemy.models.fields import JSON
from nailgun.db.sqlalchemy.models.fields import LowercaseString


class NetworkingConfig(Base):
    __tablename__ = 'networking_configs'

    id = Column(Integer, primary_key=True)
    discriminator = Column(String(50))
    cluster_id = Column(
        Integer,
        ForeignKey('clusters.id', ondelete="CASCADE")
    )
    dns_nameservers = Column(JSON, default=[
        "8.8.4.4",
        "8.8.8.8"
    ])
    floating_ranges = Column(JSON, default=[])

    __mapper_args__ = {
        'polymorphic_on': discriminator
    }


class NeutronConfig(NetworkingConfig):
    __tablename__ = 'neutron_config'
    __mapper_args__ = {
        'polymorphic_identity': 'neutron_config',
    }

    id = Column(Integer, ForeignKey('networking_configs.id'), primary_key=True)

    vlan_range = Column(JSON, default=[])
    gre_id_range = Column(JSON, default=[])
    base_mac = Column(LowercaseString(17), nullable=False)
    internal_cidr = Column(String(25))
    internal_gateway = Column(String(25))

    segmentation_type = Column(
        Enum(*consts.NEUTRON_SEGMENT_TYPES,
             name='segmentation_type'),
        nullable=False,
        default=consts.NEUTRON_SEGMENT_TYPES.vlan
    )
    net_l23_provider = Column(
        Enum(*consts.NEUTRON_L23_PROVIDERS, name='net_l23_provider'),
        nullable=False,
        default=consts.NEUTRON_L23_PROVIDERS.ovs
    )


class NovaNetworkConfig(NetworkingConfig):
    __tablename__ = 'nova_network_config'
    __mapper_args__ = {
        'polymorphic_identity': 'nova_network_config',
    }

    id = Column(Integer, ForeignKey('networking_configs.id'), primary_key=True)

    fixed_networks_cidr = Column(String(25))
    fixed_networks_vlan_start = Column(Integer)
    fixed_network_size = Column(Integer, nullable=False, default=256)
    fixed_networks_amount = Column(Integer, nullable=False, default=1)

    net_manager = Column(
        Enum(*consts.NOVA_NET_MANAGERS, name='cluster_net_manager'),
        nullable=False,
        default=consts.NOVA_NET_MANAGERS.FlatDHCPManager
    )
