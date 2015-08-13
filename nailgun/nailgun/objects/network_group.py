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
from nailgun.logger import logger


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
        notation = instance.meta.get('notation')

        # if notation data is present change ip ranges and remove
        # stalled ip adresses for the network group
        if notation:
            cls.cleanup(instance)

        if notation == 'ip_ranges' and data.get('meta', {}).get('ip_range'):
            cls._update_ip_range(instance.id, data['meta']['ip_range'])

        if notation == 'cidr' and data.get('cidr'):
            if instance.gateway is not None:
                use_gateway = True
            else:
                use_gateway = False

            cls._update_ip_range_for_cidr(
                instance.id, data.get('cidr'), use_gateway)

            cluster = instance.nodegroup.cluster
            Cluster.add_pending_changes(cluster, 'networks')

        return super(NetworkGroup, cls).update(instance, data)

    @classmethod
    def _update_ip_range(cls, network_group_id, ip_range):
        # delete old ip range
        db().query(models.IPAddrRange).filter_by(
            network_group_id=network_group_id).delete()

        new_ip_range = models.IPAddrRange(
            network_group_id=network_group_id,
            first=ip_range[0],
            last=ip_range[1])

        db().add(new_ip_range)
        db().flush()

    @classmethod
    def _update_ip_range_for_cidr(cls, network_group_id, cidr, use_gateway):
        # delete old ip range
        db().query(models.IPAddrRange).filter_by(
            network_group_id=network_group_id).delete()

        first_idx = 2 if use_gateway else 1
        new_cidr = IPNetwork(cidr)

        new_ip_range = models.IPAddrRange(
            network_group_id=network_group_id,
            first=str(new_cidr[first_idx]),
            last=str(new_cidr[-2]))

        db().add(new_ip_range)
        db().flush()

    @classmethod
    def delete(cls, instance):
        """Delete network group and do cleanup: remove ip range and
        ip adresses associated with the group
        """
        # NOTE(aroma): ip range data will be removing from db
        # automatically due to relations restrictions

        cls.cleanup(instance)
        super(NetworkGroup, cls).delete(instance)

    @classmethod
    def cleanup(cls, instance):
        """Remove all IPs that were assigned for the network group
        """
        logger.debug("Deleting old IPs for network with id=%s, cidr=%s",
                     instance.id, instance.cidr)
        db().query(models.IPAddr)\
            .filter_by(network=instance.id)\
            .delete()
        db().flush()


class NetworkGroupCollection(NailgunCollection):

    single = NetworkGroup
