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

from nailgun.objects.serializers.base import BasicSerializer


class ComponentSerializer(BasicSerializer):

    fields = (
        "id",
        "name",
        "type",
        "plugin_id"
    )

    @classmethod
    def serialize(cls, instance, fields=None):
        data_dict = BasicSerializer.serialize(
            instance, fields=fields if fields else cls.fields)
        data_dict.setdefault('compatible', {})
        data_dict['compatible'] = {
            'hypervisors': instance.hypervisors,
            'networks': instance.networks,
            'storages': instance.storages,
            'additional_services': instance.additional_services
        }
        data_dict['releases_ids'] = [r.id for r in instance.releases]

        return data_dict
