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
from nailgun.plugins.manager import PluginManager
from nailgun.objects.serializers.base import BasicSerializer
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

    # FIXME: write tests
    @classmethod
    def create_attributes(cls, instance):
        # set attributes for NICs with default attributes
        # merge interface_properties and attributes
        # populate node_nic_interface_cluster_plugin table with interfaces
        instance.attributes = instance.node.cluster.release.nic_metadata
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
        # FIXME:
        #   Use PluginManager as entry point
        #   merge interface_properties and attributes
        #   get default attributes for NodeNICInterfaceClusterPlugin
        default_attributes = instance.node.cluster.release.nic_metadata

        return default_attributes

    # FIXME: write tests
    @classmethod
    def set_attributes(cls, instance, attributes):
        """Update data for native and plugin attributes for interface.

        :param instance: NodeNICInterface instance
        :type instance: NodeNICInterface model
        :param attributes: NodeNICInterface attributes
        :type attributes: dict
        :returns: None
        """
        instance.attributes = utils.dict_merge(instance.attributes, attributes)
        # FIXME:
        #   Use PluginManager as entry point
        #   separate attributes for native and plugins
        #   set attributes for NodeNICInterfaceClusterPlugin


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
