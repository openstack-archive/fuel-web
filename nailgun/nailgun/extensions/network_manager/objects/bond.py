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
from nailgun import utils


class Bond(DPDKMixin, NailgunObject):

    model = models.NodeBondInterface
    serializer = BasicSerializer

    @classmethod
    def create(cls, data):
        bond = super(Bond, cls).create(data)
        bond = PluginManager.add_plugin_attributes_for_bond(bond)

        return bond

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
        attributes = data.pop('attributes', None)
        if attributes:
            PluginManager.update_bond_attributes(attributes)
            instance.attributes = utils.dict_merge(
                instance.attributes, attributes)
        instance.offloading_modes = data.get('offloading_modes', {})

        return super(Bond, cls).update(instance, data)

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
        :returns: dict -- Object of bond attributes
        """
        attributes = copy.deepcopy(instance.attributes)
        attributes = utils.dict_merge(
            attributes,
            PluginManager.get_bond_attributes(instance))

        return attributes

    @classmethod
    def get_bond_default_attributes(cls, cluster):
        """Get native and plugin default attributes for bond.

        :param cluster: A cluster instance
        :type cluster: Cluster model
        :returns: dict -- Object of bond default attributes
        """
        default_attributes = cluster.release.bond_attributes
        default_attributes = utils.dict_merge(
            default_attributes,
            PluginManager.get_bond_default_attributes(cluster))

        return default_attributes


class BondCollection(NailgunCollection):

    single = Bond
