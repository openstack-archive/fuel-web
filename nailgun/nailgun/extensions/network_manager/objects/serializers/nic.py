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

from distutils.version import StrictVersion

from nailgun import consts

from nailgun.objects.serializers.base import BasicSerializer
from nailgun.settings import settings


class NodeInterfacesSerializer(BasicSerializer):

    nic_fields = (
        'id',
        'mac',
        'name',
        'type',
        'state',
        'current_speed',
        'max_speed',
        'assigned_networks',
        'driver',
        'bus_info',
        'meta',
        'pxe'
    )
    bond_fields = (
        'mac',
        'name',
        'type',
        'mode',
        'state',
        'assigned_networks'
    )

    nic_fields_60 = (
        'id',
        'mac',
        'name',
        'type',
        'state',
        'current_speed',
        'max_speed',
        'assigned_networks',
        'driver',
        'bus_info',
    )
    bond_fields_60 = (
        'mac',
        'name',
        'type',
        'mode',
        'state',
        'assigned_networks'
    )

    @classmethod
    def _get_env_version(cls, instance):
        """Returns environment's version.

        Returns current Fuel version by default.
        """
        if instance.node.cluster:
            return instance.node.cluster.release.environment_version
        return settings.VERSION["release"]

    @classmethod
    def serialize_nic_interface(cls, instance, fields=None):
        from nailgun.extensions.network_manager.objects.interface import NIC
        if not fields:
            if StrictVersion(cls._get_env_version(instance)) < \
                    StrictVersion('6.1'):
                fields = cls.nic_fields_60
            else:
                fields = cls.nic_fields
        data_dict = BasicSerializer.serialize(instance, fields=fields)
        data_dict['attributes'] = NIC.get_attributes(instance)

        return data_dict

    @classmethod
    def serialize_bond_interface(cls, instance, fields=None):
        from nailgun.extensions.network_manager.objects.bond import Bond
        if not fields:
            if StrictVersion(cls._get_env_version(instance)) < \
                    StrictVersion('6.1'):
                fields = cls.bond_fields_60
            else:
                fields = cls.bond_fields
        data_dict = BasicSerializer.serialize(instance, fields=fields)
        data_dict['slaves'] = [{'name': s.name} for s in instance.slaves]
        data_dict['attributes'] = Bond.get_attributes(instance)
        data_dict['meta'] = Bond.get_meta(instance)

        return data_dict

    @classmethod
    def serialize(cls, instance, fields=None):
        iface_types = consts.NETWORK_INTERFACE_TYPES
        if instance.type == iface_types.ether:
            return cls.serialize_nic_interface(instance, fields)
        elif instance.type == iface_types.bond:
            return cls.serialize_bond_interface(instance, fields)
