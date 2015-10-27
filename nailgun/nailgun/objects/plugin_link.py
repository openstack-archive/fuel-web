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

from nailgun.db.sqlalchemy.models import plugin_link as plugin_link_db_model
from nailgun.objects.base import NailgunCollection
from nailgun.objects.base import NailgunObject
from nailgun.objects.serializers import plugin_link


class PluginLink(NailgunObject):

    model = plugin_link_db_model.PluginLink
    serializer = plugin_link.PluginLinkSerializer


class PluginLinkCollection(NailgunCollection):

    single = PluginLink

    @classmethod
    def get_by_plugin_id(cls, plugin_id):
        if plugin_id is not None:
            return cls.filter_by(None, plugin_id=plugin_id)
        else:
            return cls.all()

    @classmethod
    def create_with_plugin_id(cls, data, plugin_id):
        data['plugin_id'] = plugin_id
        return cls.create(data)
