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

from sqlalchemy.sql import not_

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects.base import NailgunCollection
from nailgun.objects.base import NailgunObject
from nailgun.objects.serializers.base import BasicSerializer
from nailgun.plugins.manager import PluginManager
from nailgun import utils


class NIC(NailgunObject):

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
    def is_sriov_enabled(cls, instance):
        sriov = instance.interface_properties.get('sriov')
        return sriov and sriov['enabled']

    # FIXME: write tests
    @classmethod
    def create_attributes(cls, instance):
        """Create attributes for interface with default values.

        :param instance: NodeNICInterface instance
        :type instance: NodeNICInterface model
        :returns: None
        """
        attributes = copy.deepcopy(
            instance.node.cluster.release.nic_metadata)
        # set attributes for NICs with interface properties as default values
        properties = instance.interface_properties
        for prop in properties:
            if prop in attributes:
                attributes[prop]['value'] = properties[prop]

        instance.attributes = attributes
        PluginManager.add_plugin_attributes_for_interface(instance)

        db().flush()

    # FIXME: write tests
    @classmethod
    def get_attributes(cls, instance):
        """Get all attributes for interface.

        :param instance: NodeNICInterface instance
        :type instance: NodeNICInterface model
        :returns: dict -- Object of interface attributes
        """
        attributes = copy.deepcopy(instance.attributes)
        attributes.update(
            PluginManager.get_nic_attributes(instance))

        return attributes

    # FIXME: write tests
    @classmethod
    def get_default_attributes(cls, instance):
        """Get default attributes for interface.

        :param instance: NodeNICInterface instance
        :type instance: NodeNICInterface model
        :returns: dict -- Dict object of NIC attributes
        """
        default_attributes = copy.deepcopy(
            instance.node.cluster.release.nic_metadata)
        # set attributes for NICs with interface properties as default values
        properties = instance.interface_properties
        for prop in properties:
            if prop in default_attributes:
                default_attributes[prop]['value'] = properties[prop]
        # FIXME:
        #   Use PluginManager as entry point
        #   get default attributes for NodeNICInterfaceClusterPlugin

        return default_attributes

    @classmethod
    def update(cls, instance, data):
        """Update data for native and plugin attributes for interface.

        :param instance: NodeNICInterface instance
        :type instance: NodeNICInterface model
        :param data: Data to update
        :type data: dict
        :returns: None
        """
        super(NIC, cls).update(instance, data)
        attributes = data.get('attributes')
        if attributes:
            PluginManager.update_nic_attributes(instance, attributes)
            instance.attributes = utils.dict_merge(
                instance.attributes, attributes)


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
