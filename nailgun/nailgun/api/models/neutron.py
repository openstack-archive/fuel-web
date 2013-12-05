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
from sqlalchemy import ForeignKey
from sqlalchemy import Integer

from nailgun.api.models.base import Base
from nailgun.api.models.fields import JSON
from nailgun.api.models.network import NetworkConfiguration
from nailgun.api.models.network import NetworkGroup
from nailgun.db import db


class NeutronNetworkConfiguration(NetworkConfiguration):
    @classmethod
    def update(cls, cluster, network_configuration):
        from nailgun.network.neutron import NeutronManager
        network_manager = NeutronManager()
        if 'networks' in network_configuration:
            for ng in network_configuration['networks']:
                if ng['id'] == network_manager.get_admin_network_group_id():
                    continue

                ng_db = db().query(NetworkGroup).get(ng['id'])

                for key, value in ng.iteritems():
                    if key == "ip_ranges":
                        cls._set_ip_ranges(ng['id'], value)
                    else:
                        if key == 'cidr' and \
                                ng['name'] not in ('private', 'public'):
                            network_manager.update_range_mask_from_cidr(
                                ng_db, value)

                        setattr(ng_db, key, value)

                if ng['name'] == 'public':
                    cls.update_cidr_from_gw_mask(ng_db, ng)
                    #TODO(NAME) get rid of unmanaged parameters in request
                    if 'neutron_parameters' in network_configuration:
                        pre_nets = network_configuration[
                            'neutron_parameters']['predefined_networks']
                        pre_nets['net04_ext']['L3']['gateway'] = ng['gateway']
                if ng['name'] != 'private':
                    network_manager.create_networks(ng_db)
                ng_db.cluster.add_pending_changes('networks')

        if 'neutron_parameters' in network_configuration:
            for key, value in network_configuration['neutron_parameters'] \
                    .items():
                setattr(cluster.neutron_config, key, value)
            db().add(cluster.neutron_config)
            db().commit()

    @classmethod
    def update_cidr_from_gw_mask(cls, ng_db, ng):
        if ng.get('gateway') and ng.get('netmask'):
            from nailgun.network.checker import calc_cidr_from_gw_mask
            cidr = calc_cidr_from_gw_mask({'gateway': ng['gateway'],
                                           'netmask': ng['netmask']})
            if cidr:
                ng_db.cidr = str(cidr)
                ng_db.network_size = cidr.size


class NeutronConfig(Base):
    __tablename__ = 'neutron_configs'
    NET_SEGMENT_TYPES = ('vlan', 'gre')
    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, ForeignKey('clusters.id'))
    parameters = Column(JSON, default={})
    L2 = Column(JSON, default={})
    L3 = Column(JSON, default={})
    predefined_networks = Column(JSON, default={})

    segmentation_type = Column(
        Enum(*NET_SEGMENT_TYPES,
             name='segmentation_type'),
        nullable=False,
        default='vlan'
    )
