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

import copy

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.extensions.network_manager.objects.interface import DPDKMixin
from nailgun.extensions.network_manager.objects.interface import NIC
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.base import BasicSerializer
from nailgun.plugins.manager import PluginManager


class Bond(DPDKMixin, NailgunObject):

    model = models.NodeBondInterface
    serializer = BasicSerializer

    #@classmethod
    #def create(cls, data):
    #    bond = super(Bond, cls).create(data)
    #    cls.create_attributes(bond)
    #
    #    return bond

    # FIXME: write tests
    @classmethod
    def create_attributes(cls, instance):
        """Create attributes for bond with default values.

        :param instance: NodeNICInterface instance
        :type instance: NodeNICInterface model
        :returns: None
        """
        attributes = copy.deepcopy(
            instance.node.cluster.release.bond_attributes)
        # set attributes for NICs with interface properties as default values
        properties = instance.bond_properties
        for prop in properties:
            if prop in attributes:
                attributes[prop]['value'] = properties[prop]

        instance.attributes = attributes
        PluginManager.add_plugin_attributes_for_bond(instance)

        db().flush()

    @classmethod
    def assign_networks(cls, instance, networks):
        """Assigns networks to specified Bond interface.

        :param instance: Bond object
        :type instance: Bond model
        :param networks: List of networks to assign
        :type networks: list
        :returns: None
        """
        instance.assigned_networks_list = networks

    @classmethod
    def update(cls, instance, data):
        """Update existing Bond with specified parameters.

        :param instance: object (model) instance
        :param data: dictionary of key-value pairs as object fields
        :returns: instance of an object (model)
        """
        instance.update(data)
        instance.offloading_modes = data.get('offloading_modes', {})
        return instance

    @classmethod
    def dpdk_available(cls, instance, dpdk_drivers):
        return all(NIC.get_dpdk_driver(iface, dpdk_drivers)
                   for iface in instance.slaves)

    @classmethod
    def get_bond_interfaces_for_all_nodes(cls, cluster, networks=None):
        bond_interfaces_query = db().query(
            models.NodeBondInterface
        ).join(
            models.Node
        ).filter(
            models.Node.cluster_id == cluster.id
        )
        if networks:
            bond_interfaces_query = bond_interfaces_query.join(
                models.NodeBondInterface.assigned_networks_list,
                aliased=True).filter(models.NetworkGroup.id.in_(networks))
        return bond_interfaces_query.all()

    @classmethod
    def get_attributes(cls, instance):
        """Get native and plugin attributes for bond.

        :param instance: NodeBondInterface instance
        :type instance: NodeBondInterface model
        :returns: dict -- Object of interface attributes
        """
        attributes = copy.deepcopy(instance.attributes)
        attributes.update(
            PluginManager.get_bond_attributes(instance))

        return attributes


class BondCollection(NailgunCollection):

    single = Bond
