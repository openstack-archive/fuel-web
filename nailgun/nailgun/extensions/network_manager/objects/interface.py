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

from nailgun import consts
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
        return bool(dpdk and dpdk.get('enabled'))

    @classmethod
    def refresh_interface_dpdk_properties(cls, interface, dpdk_drivers):
        interface_properties = interface.interface_properties
        dpdk_properties = interface_properties.get('dpdk', {}).copy()
        dpdk_properties['available'] = cls.dpdk_available(interface,
                                                          dpdk_drivers)
        if (not dpdk_properties['available'] and
                dpdk_properties.get('enabled')):
            dpdk_properties['enabled'] = False
        # update interface_properties in DB only if something was changed
        if interface_properties.get('dpdk', {}) != dpdk_properties:
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
        """Checks availability of DPDK for given interface.

        DPDK availability of the interface depends on presence of DPDK drivers
        and libraries for particular NIC. It may vary for different OpenStack
        releases. So, dpdk_drivers vary for different releases and it can be
        not empty only for node that is assigned to cluster currently. Also,
        DPDK is only supported for Neutron with VLAN segmentation currently.

        :param instance: NodeNICInterface instance
        :param dpdk_drivers: DPDK drivers to PCI_ID mapping for cluster node is
                             currently assigned to (dict)
        :return: True if DPDK is available
        """
        return (cls.get_dpdk_driver(instance, dpdk_drivers) is not None and
                instance.node.cluster.network_config.segmentation_type ==
                consts.NEUTRON_SEGMENT_TYPES.vlan)

    @classmethod
    def is_sriov_enabled(cls, instance):
        sriov = instance.interface_properties.get('sriov')
        return sriov and sriov['enabled']

    @classmethod
    def update_offloading_modes(cls, instance, new_modes, keep_states=False):
        """Update information about offloading modes for the interface.

        :param instance: Interface object
        :param new_modes: New offloading modes
        :param keep_states: If True, information about available modes will be
               updated, but states configured by user will not be overwritten.
        """
        if keep_states:
            old_modes_states = instance.offloading_modes_as_flat_dict(
                instance.offloading_modes)
            for mode in new_modes:
                if mode["name"] in old_modes_states:
                    mode["state"] = old_modes_states[mode["name"]]
        instance.offloading_modes = new_modes


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
