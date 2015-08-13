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

from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject


class NetworkGroup(NailgunObject):

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

    @classmethod
    def update(cls, instance, data):
        # to avoid circular imports
        from nailgun.network.manager import NetworkManager

        notation = instance.meta.get('notation')

        # if notation data is present change ip ranges and remove
        # stalled ip adresses for the network group
        if notation:
            NetworkManager.cleanup_network_group(instance)

        notation = data['meta']['notation'] \
            if 'notation' in data.get('meta', {}) else notation

        NetworkManager._set_ip_ranges_on_notation(notation, instance, data)

        cluster = instance.nodegroup.cluster
        Cluster.add_pending_changes(cluster, 'networks')

        # remove 'ip_ranges' (if) any from data as this is relation
        # attribute for the orm model object
        if data.get('ip_ranges'):
            del(data['ip_ranges'])
        return super(NetworkGroup, cls).update(instance, data)

    @classmethod
    def delete(cls, instance):
        """Delete network group and do cleanup: remove ip range and
        ip adresses associated with the group
        """
        # NOTE(aroma): ip range data will be removing from db
        # automatically due to relations restrictions

        # to avoid circular imports
        from nailgun.network.manager import NetworkManager

        NetworkManager.cleanup_network_group(instance)

        super(NetworkGroup, cls).delete(instance)


class NetworkGroupCollection(NailgunCollection):

    single = NetworkGroup
