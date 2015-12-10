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

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.network_group import NetworkGroupSerializer


class NetworkGroup(NailgunObject):

    model = models.NetworkGroup
    serializer = NetworkGroupSerializer

    @classmethod
    def get_from_node_group_by_name(cls, node_group_id, network_name):
        ng = db().query(models.NetworkGroup).filter_by(group_id=node_group_id,
                                                       name=network_name)
        return ng.first() if ng else None

    @classmethod
    def get_default_admin_network(cls):
        return db().query(models.NetworkGroup)\
            .filter_by(name=consts.NETWORKS.fuelweb_admin)\
            .filter_by(group_id=None)\
            .first()

    @classmethod
    def create(cls, data):
        """Create NetworkGroup instance with specified parameters in DB.

        Create corresponding IPAddrRange instance with IP range specified in
        data or calculated from CIDR if not specified.

        :param data: dictionary of key-value pairs as NetworkGroup fields
        :returns: instance of new NetworkGroup
        """
        instance = super(NetworkGroup, cls).create(data)
        cls._create_ip_ranges_on_notation(instance)
        cls._reassign_template_networks(instance)
        db().refresh(instance)
        return instance

    @classmethod
    def update(cls, instance, data):
        # preserve input to original data
        data = dict(data)

        # cleanup stalled data and generate new for the group
        # the function refresh the instance from db, so
        # should to be invoked first
        cls._regenerate_ip_ranges_on_notation(instance, data)

        # remove 'ip_ranges' (if) any from data as this is relation
        # attribute for the orm model object
        data.pop('ip_ranges', None)

        # remove 'meta' key because we'll update meta manually
        meta = data.pop('meta', {})

        # only 'notation' and 'use_gateway' attributes is
        # allowed to be updated in network group metadata for
        # old clusters so here we updated it manually with data
        # which doesn't contain 'meta' key
        for param in ('notation', 'use_gateway'):
            if param in meta:
                instance.meta[param] = meta[param]

        return super(NetworkGroup, cls).update(instance, data)

    @classmethod
    def delete(cls, instance):
        notation = instance.meta.get('notation')
        if notation and not instance.nodegroup.cluster.is_locked:
            cls._delete_ips(instance)
        db().delete(instance)
        db().flush()

    @classmethod
    def is_untagged(cls, instance):
        """Return True if network is untagged"""
        return (instance.vlan_start is None) \
            and not instance.meta.get('neutron_vlan_range') \
            and not instance.meta.get('ext_net_data')

    @classmethod
    def _create_ip_ranges_on_notation(cls, instance):
        """Create IP-address ranges basing on 'notation' field of 'meta' field

        :param instance: NetworkGroup instance
        :type instance: models.NetworkGroup
        :return: None
        """
        notation = instance.meta.get("notation")
        if notation:
            try:
                if notation == 'cidr':
                    cls._update_range_from_cidr(
                        instance, IPNetwork(instance.cidr).cidr,
                        instance.meta.get('use_gateway'))
                elif notation == 'ip_ranges' and instance.meta.get("ip_range"):
                    cls._set_ip_ranges(instance, [instance.meta["ip_range"]])
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

    @classmethod
    def _regenerate_ip_ranges_on_notation(cls, instance, data):
        """Regenerate IP-address ranges

        This method regenerates IPs based on 'notation' field of
        Network group 'meta' content.

        :param instance: NetworkGroup instance
        :type instance: models.NetworkGroup
        :param data: network data
        :type data: dict
        :return: None
        """
        notation = instance.meta['notation']
        data_meta = data.get('meta', {})

        notation = data_meta.get('notation', notation)
        if notation == consts.NETWORK_NOTATION.ip_ranges:
            ip_ranges = data.get("ip_ranges") or \
                [(r.first, r.last) for r in instance.ip_ranges]
            cls._set_ip_ranges(instance, ip_ranges)

        elif notation == consts.NETWORK_NOTATION.cidr:
            use_gateway = data_meta.get(
                'use_gateway', instance.meta.get('use_gateway'))
            cidr = data.get('cidr', instance.cidr)
            cls._update_range_from_cidr(
                instance, cidr, use_gateway=use_gateway)
        else:
            return
        # as ip ranges were regenerated we must update instance object
        # in order to prevent possible SQAlchemy errors with operating
        # on stale data
        db().refresh(instance)

    @classmethod
    def _set_ip_ranges(cls, instance, ip_ranges):
        """Set IP-address ranges.

        :param instance: NetworkGroup instance being updated
        :type instance: models.NetworkGroup
        :param ip_ranges: IP-address ranges sequence
        :type ip_ranges: iterable of pairs
        :return: None
        """
        # deleting old ip ranges
        db().query(models.IPAddrRange).filter_by(
            network_group_id=instance.id).delete()

        for r in ip_ranges:
            new_ip_range = models.IPAddrRange(
                first=r[0],
                last=r[1],
                network_group_id=instance.id)
            db().add(new_ip_range)
        db().refresh(instance)
        db().flush()

    @classmethod
    def _update_range_from_cidr(
            cls, instance, cidr, use_gateway=False):
        """Update network ranges for CIDR.

        :param instance: NetworkGroup instance being updated
        :type instance: models.NetworkGroup
        :param cidr: CIDR network representation
        :type cidr: basestring
        :param use_gateway: whether gateway is taken into account
        :type use_gateway: bool
        :return: None
        """
        first_idx = 2 if use_gateway else 1
        new_cidr = IPNetwork(cidr)
        ip_range = (str(new_cidr[first_idx]), str(new_cidr[-2]))
        cls._set_ip_ranges(instance, [ip_range])

    @classmethod
    def _delete_ips(cls, instance):
        """Network group cleanup

        Deletes all IPs which were assigned within the network group.

        :param instance: NetworkGroup instance
        :type  instance: models.NetworkGroup
        :returns: None
        """
        logger.debug("Deleting old IPs for network with id=%s, cidr=%s",
                     instance.id, instance.cidr)
        db().query(models.IPAddr).filter(
            models.IPAddr.network == instance.id
        ).delete()
        db().flush()

    @classmethod
    def _reassign_template_networks(cls, instance):
        cluster = instance.nodegroup.cluster
        if not cluster.network_config.configuration_template:
            return

        nm = Cluster.get_network_manager(cluster)
        for node in cluster.nodes:
            nm.assign_networks_by_template(node)


class NetworkGroupCollection(NailgunCollection):

    single = NetworkGroup
