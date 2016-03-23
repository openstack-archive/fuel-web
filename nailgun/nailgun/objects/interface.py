# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

import six
from sqlalchemy.sql import not_

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.base import BasicSerializer


class DPDKMixin(object):

    @classmethod
    def dpdk_available(cls, instance, dpdk_drivers):
        raise NotImplementedError

    @classmethod
    def dpdk_enabled(cls, instance):
        dpdk = instance.interface_properties.get('dpdk')
        return dpdk and dpdk.get('enabled')

    @classmethod
    def refresh_interface_dpdk_properties(cls, interface, dpdk_drivers):
        interface_properties = interface.interface_properties
        dpdk_properties = interface_properties.get('dpdk', {})
        dpdk_properties['available'] = cls.dpdk_available(interface,
                                                          dpdk_drivers)
        if (not dpdk_properties['available'] and
                dpdk_properties.get('enabled')):
            dpdk_properties['enabled'] = False
        interface_properties['dpdk'] = dpdk_properties


class NIC(DPDKMixin, NailgunObject):

    model = models.NodeNICInterface
    serializer = BasicSerializer

    @classmethod
    def assign_networks(cls, instance, networks):
        """Assigns networks to specified interface.

        :param instance: Interface object
        :type instance: Interface model
        :param networks: List of networks to assign
        :type networks: list
        :returns: None
        """
        instance.assigned_networks_list = networks
        db().flush()

    @classmethod
    def get_dpdk_driver(cls, instance, dpdk_drivers):
        pci_id = instance.interface_properties.get('pci_id', '').lower()
        for driver, device_ids in six.iteritems(dpdk_drivers):
            if pci_id in device_ids:
                return driver
        return None

    @classmethod
    def dpdk_available(cls, instance, dpdk_drivers):
        return cls.get_dpdk_driver(instance, dpdk_drivers) is not None

    @classmethod
    def is_sriov_enabled(cls, instance):
        sriov = instance.interface_properties.get('sriov')
        return sriov and sriov['enabled']


class NICCollection(NailgunCollection):

    single = NIC

    @classmethod
    def get_interfaces_not_in_mac_list(cls, node_id, mac_addresses):
        """Find all interfaces with MAC address not in mac_addresses.

        :param node_id: Node ID
        :type node_id: int
        :param mac_addresses: list of MAC addresses
        :type mac_addresses: list
        :returns: iterable (SQLAlchemy query)
        """
        return db().query(models.NodeNICInterface).filter(
            models.NodeNICInterface.node_id == node_id
        ).filter(
            not_(models.NodeNICInterface.mac.in_(mac_addresses))
        )
