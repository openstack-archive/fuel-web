# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from nailgun.objects.serializers.base import BasicSerializer


class NodeSerializer(BasicSerializer):

    fields = (
        'id',
        'name',
        'meta',
        'progress',
        'kernel_params',
        'roles',
        'pending_roles',
        'status',
        'mac',
        'hostname',
        'ip',
        'manufacturer',
        'platform_name',
        'pending_addition',
        'pending_deletion',
        'os_platform',
        'error_type',
        'online',
        'labels',
        'cluster',
        'network_data',
        'group_id'
    )

    @classmethod
    def serialize(cls, instance, fields=None):
        from nailgun.objects import Node
        data_dict = super(NodeSerializer, cls).serialize(instance, fields)
        data_dict['fqdn'] = Node.get_node_fqdn(instance)
        return data_dict
