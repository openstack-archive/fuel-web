# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

from netaddr import IPNetwork

from nailgun.objects.serializers.network_group import NetworkGroupSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun import objects


class NetworkGroup(objects.NailgunObject):

    model = models.NetworkGroup
    serializer = NetworkGroupSerializer

    @classmethod
    def get_from_node_group_by_name(cls, node_group_id, network_name):
        ng = db().query(models.NetworkGroup).filter_by(group_id=node_group_id,
                                                       name=network_name)
        return ng.first() if ng else None

    @classmethod
    def create(cls, data):
        """Create NetworkGroup instance with specified parameters in DB.
        Create corresponding IPAddrRange instance with IP range specified in
        data or calculated from CIDR if not specified.

        :param data: dictionary of key-value pairs as NetworkGroup fields
        :returns: instance of new NetworkGroup
        """
        instance = super(NetworkGroup, cls).create(data)
        notation = instance.meta.get('notation')
        if notation:
            ip_range = models.IPAddrRange(network_group_id=instance.id)
            try:
                if notation == 'cidr':
                    cidr = IPNetwork(instance.cidr).cidr
                    ip_range.first = str(cidr[2])
                    ip_range.last = str(cidr[-2])
                elif notation == 'ip_ranges' and instance.meta.get('ip_range'):
                    ip_range.first = instance.meta['ip_range'][0]
                    ip_range.last = instance.meta['ip_range'][1]
                else:
                    raise errors.CannotCreate()
            except (
                errors.CannotCreate,
                IndexError,
                TypeError
            ):
                raise errors.CannotCreate(
                    "IPAddrRange object cannot be created for network '{0}' "
                    "with notation='{1}', ip_range='{2}'".format(
                        instance.name,
                        instance.meta.get('notation'),
                        instance.meta.get('ip_range'))
                )
            db().add(ip_range)
            db().flush()
        return instance


class NetworkGroupCollection(objects.NailgunCollection):

    single = NetworkGroup
