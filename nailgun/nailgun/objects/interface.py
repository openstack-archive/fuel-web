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


from sqlalchemy.sql import not_

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.base import BasicSerializer


class NIC(NailgunObject):

    model = models.NodeNICInterface
    serializer = BasicSerializer

    @classmethod
    def replace_assigned_networks(cls, instance, assigned_nets):
        """Replaces assigned networks list for specified interface.

        :param instance: Interface object
        :type instance: Interface model
        :returns: None
        """
        db().query(models.NetworkNICAssignment).filter_by(
            interface_id=instance.id
        ).delete()
        for net in assigned_nets:
            net_assignment = models.NetworkNICAssignment()
            net_assignment.network_id = net['id']
            net_assignment.interface_id = instance.id
            db().add(net_assignment)
        db().flush()


class NICCollection(NailgunCollection):

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
        return db().query(models.NodeNICInterface).filter(
            models.NodeNICInterface.node_id == node_id
        ).filter(
            not_(models.NodeNICInterface.mac.in_(mac_addresses))
        )
