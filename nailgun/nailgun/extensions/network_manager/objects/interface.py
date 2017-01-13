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

import copy

import six
from sqlalchemy.sql import not_

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.base import BasicSerializer
from nailgun.plugins.manager import PluginManager
from nailgun import utils


class DPDKMixin(object):

    @classmethod
    def dpdk_available(cls, instance, dpdk_drivers):
        raise NotImplementedError

    @classmethod
    def dpdk_enabled(cls, instance):
        return bool(instance.attributes.get('dpdk', {}).get(
            'enabled', {}).get('value'))

    @classmethod
    def refresh_interface_dpdk_properties(cls, interface, dpdk_drivers):
        attributes = interface.attributes
        dpdk_attributes = copy.deepcopy(attributes.get('dpdk', {}))
        dpdk_available = cls.dpdk_available(interface, dpdk_drivers)

        if (not dpdk_available and dpdk_attributes.get(
                'enabled', {}).get('value')):
            dpdk_attributes['enabled']['value'] = False
        # update attributes in DB only if something was changed
        if attributes.get('dpdk', {}) != dpdk_attributes:
            attributes['dpdk'] = dpdk_attributes
        if 'meta' in interface:
            meta = interface.meta
            if meta.get('dpdk', {}) != {'available': dpdk_available}:
                meta['dpdk'] = {'available': dpdk_available}


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
        from nailgun.objects import Node
        pci_id = instance.meta.get('pci_id', '').lower()
        sriov_enabled = Node.sriov_enabled(instance.node)
        for driver, device_ids in six.iteritems(dpdk_drivers):
            if pci_id in device_ids:
                if sriov_enabled:
                    return consts.DPDK_DRIVER_IN_SRIOV_CASE
                return driver
        return None

    @classmethod
    def get_dpdk_queues_count(cls, instance):
        dpdk_cpu_pinning = utils.get_in(instance.node.attributes,
                                        'cpu_pinning', 'dpdk', 'value') or 0
        max_queues = utils.get_in(instance.meta, 'max_queues') or 0
        # Number CPU for ovs_pmd_core_mask equals number DPDK CPU pinning - 1
        # 1 CPU is needed for ovs_core_mask
        pmd_core_count = dpdk_cpu_pinning - 1 if dpdk_cpu_pinning > 0 else 0
        return min(max_queues, pmd_core_count)

    @classmethod
    def dpdk_available(cls, instance, dpdk_drivers):
        """Checks availability of DPDK for given interface.

        DPDK availability of the interface depends on presence of DPDK drivers
        and libraries for particular NIC. It may vary for different OpenStack
        releases. So, dpdk_drivers vary for different releases and it can be
        not empty only for node that is assigned to cluster currently. Also,
        DPDK is only supported for Neutron with VLAN and VXLAN segmentation
        currently.
        :param instance: NodeNICInterface instance
        :param dpdk_drivers: DPDK drivers to PCI_ID mapping for cluster node is
                             currently assigned to (dict)
        :return: True if DPDK is available
        """
        return (cls.get_dpdk_driver(instance, dpdk_drivers) is not None and
                Cluster.is_dpdk_supported_for_segmentation(
                    instance.node.cluster))

    @classmethod
    def is_sriov_enabled(cls, instance):
        enabled = instance.attributes.get('sriov', {}).get('enabled')
        return enabled and enabled['value']

    @classmethod
    def get_nic_interfaces_for_all_nodes(cls, cluster, networks=None):
        nic_interfaces_query = db().query(
            models.NodeNICInterface
        ).join(
            models.Node
        ).filter(
            models.Node.cluster_id == cluster.id
        )
        if networks:
            nic_interfaces_query = nic_interfaces_query.join(
                models.NodeNICInterface.assigned_networks_list, aliased=True).\
                filter(models.NetworkGroup.id.in_(networks))
        return nic_interfaces_query.all()

    @classmethod
    def get_networks_to_interfaces_mapping_on_all_nodes(cls, cluster):
        """Query networks to interfaces mapping on all nodes in cluster.

        Returns combined results for NICs and bonds for every node.
        Names are returned for node and interface (NIC or bond),
        IDs are returned for networks. Results are sorted by node name then
        interface name.
        """
        nodes_nics_networks = db().query(
            models.Node.hostname,
            models.NodeNICInterface.name,
            models.NetworkGroup.id,
        ).join(
            models.Node.nic_interfaces,
            models.NodeNICInterface.assigned_networks_list
        ).filter(
            models.Node.cluster_id == cluster.id,
        )
        nodes_bonds_networks = db().query(
            models.Node.hostname,
            models.NodeBondInterface.name,
            models.NetworkGroup.id,
        ).join(
            models.Node.bond_interfaces,
            models.NodeBondInterface.assigned_networks_list
        ).filter(
            models.Node.cluster_id == cluster.id,
        )
        return nodes_nics_networks.union(
            nodes_bonds_networks
        ).order_by(
            # column 1 then 2 from the result. cannot call them by name as
            # names for column 2 are different in this union
            '1', '2'
        )

    @classmethod
    def get_interface_by_net_name(cls, node_id, netname):
        """Get interface with specified network assigned to it.

        This method first checks for a NodeNICInterface with the specified
        network assigned. If that fails it will look for a NodeBondInterface
        with that network assigned.

        :param instance_id: Node ID
        :param netname: NetworkGroup name
        :returns: either NodeNICInterface or NodeBondInterface
        """
        iface = db().query(models.NodeNICInterface).join(
            (models.NetworkGroup,
             models.NodeNICInterface.assigned_networks_list)
        ).filter(
            models.NetworkGroup.name == netname
        ).filter(
            models.NodeNICInterface.node_id == node_id
        ).first()
        if iface:
            return iface

        return db().query(models.NodeBondInterface).join(
            (models.NetworkGroup,
             models.NodeBondInterface.assigned_networks_list)
        ).filter(
            models.NetworkGroup.name == netname
        ).filter(
            models.NodeBondInterface.node_id == node_id
        ).first()

    @classmethod
    def get_nic_by_name(cls, node, iface_name):
        nic = db().query(models.NodeNICInterface).filter_by(
            name=iface_name
        ).filter_by(
            node_id=node.id
        ).first()

        return nic

    @classmethod
    def create_attributes(cls, instance):
        """Create attributes for interface with default values.

        :param instance: NodeNICInterface instance
        :type instance: NodeNICInterface model
        :returns: None
        """
        instance.attributes = cls._get_default_attributes(instance)
        PluginManager.add_plugin_attributes_for_interface(instance)

        db().flush()

    @classmethod
    def get_attributes(cls, instance):
        """Get all attributes for interface.

        :param instance: NodeNICInterface instance
        :type instance: NodeNICInterface model
        :returns: dict -- Object of interface attributes
        """
        attributes = copy.deepcopy(instance.attributes)
        attributes = utils.dict_merge(
            attributes,
            PluginManager.get_nic_attributes(instance))

        return attributes

    @classmethod
    def get_default_attributes(cls, instance):
        """Get default attributes for interface.

        :param instance: NodeNICInterface instance
        :type instance: NodeNICInterface model
        :returns: dict -- Dict object of NIC attributes
        """
        attributes = cls._get_default_attributes(instance)
        attributes = utils.dict_merge(
            attributes,
            PluginManager.get_nic_attributes(instance))
        attributes = utils.dict_merge(
            attributes,
            PluginManager.get_nic_default_attributes(
                instance.node.cluster))

        return attributes

    @classmethod
    def update(cls, instance, data):
        """Update data of native and plugin attributes for interface.

        :param instance: NodeNICInterface instance
        :type instance: NodeNICInterface model
        :param data: Data to update
        :type data: dict
        :returns: instance of an object (model)
        """
        attributes = data.pop('attributes', None)
        if attributes:
            PluginManager.update_nic_attributes(attributes)
            instance.attributes = utils.dict_merge(
                instance.attributes, attributes)

        return super(NIC, cls).update(instance, data)

    @classmethod
    def offloading_modes_as_flat_dict(cls, modes):
        """Represents multilevel structure of offloading modes as flat dict

        This is done to ease merging
        :param modes: list of offloading modes
        :return: flat dictionary {mode['name']: mode['state']}
        """
        result = dict()
        if modes is None:
            return result
        for mode in modes:
            result[mode["name"]] = mode["state"]
            if mode["sub"]:
                result.update(cls.offloading_modes_as_flat_dict(mode["sub"]))
        return result

    @classmethod
    def _get_default_attributes(cls, instance):
        attributes = copy.deepcopy(
            instance.node.cluster.release.nic_attributes)

        mac = instance.mac
        meta = instance.node.meta
        name = instance.name
        offloading_modes = []
        properties = {}

        for interface in meta.get('interfaces', []):
            if interface['name'] == name and interface['mac'] == mac:
                properties = interface.get('interface_properties', {})
                offloading_modes = interface.get('offloading_modes', [])

        attributes['mtu']['value']['value'] = properties.get('mtu')
        attributes['sriov']['enabled']['value'] = \
            properties.get('sriov', {}).get('enabled', False)
        attributes['sriov']['numvfs']['value'] = \
            properties.get('sriov', {}).get('sriov_numvfs')
        attributes['sriov']['physnet']['value'] = \
            properties.get('sriov', {}).get('physnet', 'physnet2')
        attributes['dpdk']['enabled']['value'] = \
            properties.get('dpdk', {}).get('enabled', False)

        offloading_modes_values = cls.offloading_modes_as_flat_dict(
            offloading_modes)
        attributes['offloading']['disable']['value'] = \
            properties.get('disable_offloading', False)
        attributes['offloading']['modes']['value'] = offloading_modes_values

        return attributes

    @classmethod
    def get_default_meta(cls, interface_properties={}):
        return {
            'offloading_modes': [],
            'sriov': {
                'available': interface_properties.get(
                    'sriov', {}).get('available', False),
                'pci_id': interface_properties.get(
                    'sriov', {}).get('pci_id', ''),
                'totalvfs': interface_properties.get(
                    'sriov', {}).get('sriov_totalvfs', 0)
            },
            'dpdk': {
                'available': interface_properties.get(
                    'dpdk', {}).get('available', False)
            },
            'pci_id': interface_properties.get('pci_id', ''),
            'numa_node': interface_properties.get('numa_node'),
            'max_queues': interface_properties.get('max_queues')
        }


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
