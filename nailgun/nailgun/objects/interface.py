# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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


from nailgun.db.sqlalchemy import models
from nailgun.network.proxy import NetworkNICAssignmentProxy
from nailgun.network.proxy import NICProxy
from nailgun.objects import ProxiedNailgunCollection
from nailgun.objects import ProxiedNailgunObject
from nailgun.objects.serializers.base import BasicSerializer


class NIC(ProxiedNailgunObject):

    model = models.NodeNICInterface
    serializer = BasicSerializer
    proxy = NICProxy()

    @classmethod
    def replace_assigned_networks(cls, instance, assigned_nets):
        """Replaces assigned networks list for specified interface.

        :param instance: Interface object
        :type instance: Interface model
        :returns: None
        """
        NetworkNICAssignment.delete_by_interface_id(instance.id)
        for net in assigned_nets:
            data = {
                'network_id': net['id'],
                'interface_id': instance.id
            }
            NetworkNICAssignment.create(data)


class NetworkNICAssignment(ProxiedNailgunObject):

    model = models.NetworkNICAssignment
    serializer = BasicSerializer
    proxy = NetworkNICAssignmentProxy()

    @classmethod
    def delete_by_interface_id(cls, interface_id):
        params = {
            'filters': [
                {'name': 'interface_id', 'op': 'eq', 'val': interface_id}
            ]
        }
        cls.proxy.filter_delete(params)


class NICCollection(ProxiedNailgunCollection):

    single = NIC

    @classmethod
    def get_interfaces_not_in_mac_list(cls, node_id, mac_addresses):
        """Find all interfaces with MAC address not in mac_addresses.

        :param node_id: Node ID
        :type node_id: int
        :param mac_addresses: list of MAC addresses
        :type mac_addresses: list
        :returns: list of NodeNICInterface
        """
        params = {
            'filters': [
                {'name': 'node_id', 'op': 'eq', 'val': node_id},
                {'not': {'name': 'mac', 'op': 'in', 'val': mac_addresses}}
            ]
        }
        return cls.single.proxy.filter(params)
