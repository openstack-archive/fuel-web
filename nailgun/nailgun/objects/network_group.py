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

from nailgun import consts
from nailgun.errors import errors

from nailgun.logger import logger

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
    def update_meta(cls, instance, data):
        """Updates particular keys in object's meta.
        Is used by NetworkManager.update_networks as
        for old clusters only those data in meta is
        allowed for updating
        """
        meta_copy = dict(instance.meta)
        meta_copy.update(data)
        instance.meta = meta_copy

    @classmethod
    def update(cls, instance, data):
        # cleaup stalled data and generate new for the group
        cls._regenerate_ip_ranges_on_notation(instance, data)

        # remove 'ip_ranges' (if) any from data as this is relation
        # attribute for the orm model object
        if data.get('ip_ranges'):
            del data['ip_ranges']
        return super(NetworkGroup, cls).update(instance, data)

    @classmethod
    def _regenerate_ip_ranges_on_notation(cls, instance, data):
        notation = instance.meta['notation']

        # if notation data is present change ip ranges and remove
        # stalled ip addresses for the network group
        if notation:
            cls._delete_ips(instance)

        notation = data['meta']['notation'] \
            if 'notation' in data.get('meta', {}) else notation

        if notation == consts.NETWORK_NOTATION.ip_ranges:
            ip_ranges = data.get("ip_ranges") or \
                [(r.first, r.last) for r in instance.ip_ranges]
            cls._set_ip_ranges(instance, ip_ranges)

        elif notation == consts.NETWORK_NOTATION.cidr:
            if data.get('meta', {}).get('use_gateway') is not None:
                use_gateway = data['meta']['use_gateway']
            else:
                use_gateway = instance.meta['use_gateway']

            cidr = data["cidr"] if "cidr" in data else instance.cidr

            cls._update_range_mask_from_cidr(
                instance, cidr, use_gateway=use_gateway)

    @classmethod
    def _set_ip_ranges(cls, instance, ip_ranges):
        # deleting old ip ranges
        db().query(models.IPAddrRange).filter_by(
            network_group_id=instance.id).delete()

        for r in ip_ranges:
            new_ip_range = models.IPAddrRange(
                first=r[0],
                last=r[1],
                network_group_id=instance.id)
            db().add(new_ip_range)
        db().flush()

    @classmethod
    def _update_range_mask_from_cidr(cls, instance, cidr,
                                     use_gateway=False):
        """Update network ranges for cidr
        """
        # deleting old ip ranges
        db().query(models.IPAddrRange).filter_by(
            network_group_id=instance.id).delete()

        first_idx = 2 if use_gateway else 1
        new_cidr = IPNetwork(cidr)
        ip_range = models.IPAddrRange(
            network_group_id=instance.id,
            first=str(new_cidr[first_idx]),
            last=str(new_cidr[-2]))

        db().add(ip_range)
        db().flush()

    @classmethod
    def delete(cls, instance):
        """Delete network group and do cleanup: remove ip range and
        ip adresses associated with the group
        """
        # NOTE(aroma): ip range data will be removing from db
        # automatically due to relations restrictions

        cls._delete_ips(instance)

        super(NetworkGroup, cls).delete(instance)

    @classmethod
    def _delete_ips(cls, instance):
        """Network group cleanup - deletes all IPs were assigned within
        the network group.

        :param nw_group: NetworkGroup object.
        :type  nw_group: NetworkGroup
        :returns: None
        """
        logger.debug("Deleting old IPs for network with id=%s, cidr=%s",
                     instance.id, instance.cidr)
        db().query(models.IPAddr).filter(
            models.IPAddr.network == instance.id
        ).delete()
        db().flush()


class NetworkGroupCollection(NailgunCollection):

    single = NetworkGroup
