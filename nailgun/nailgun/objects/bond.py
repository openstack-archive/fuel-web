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


from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.base import BasicSerializer


class Bond(NailgunObject):

    model = models.NodeBondInterface
    serializer = BasicSerializer

    @classmethod
    def assign_networks(cls, instance, networks):
        """Assigns networks to specified Bond interface.

        :param instance: Bond object
        :type instance: Bond model
        :param networks: List of networks to assign
        :type networks: list
        :returns: None
        """
        for net in networks:
            net_assignment = models.NetworkBondAssignment()
            net_assignment.network_id = net['id']
            net_assignment.bond_id = instance.id
            db().add(net_assignment)
        db().flush()

    @classmethod
    def update_offloading_modes(cls, instance, new_modes):
        """Updates offloading modes for specified Bond interface.

        :param instance: Bond object
        :type instance: Bond model
        :param new_modes: List of offloading modes
        :type new_modes: list
        :returns: None
        """
        new_modes_dict = \
            models.NodeNICInterface.offloading_modes_as_flat_dict(new_modes)
        for interface in instance.slaves:
            cls._update_modes(interface.offloading_modes, new_modes_dict)
            interface.offloading_modes.changed()
        db().flush()

    @classmethod
    def _update_modes(cls, modes, update_dict):
        for mode in modes:
            if mode['name'] in update_dict:
                mode['state'] = update_dict[mode['name']]
            if mode['sub']:
                cls._update_modes(mode['sub'], update_dict)


class BondCollection(NailgunCollection):

    single = Bond
