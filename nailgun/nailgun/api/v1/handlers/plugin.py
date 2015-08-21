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

import six

from nailgun.api.v1.handlers import base
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.validators import plugin
from nailgun.errors import errors
from nailgun import objects
from nailgun.plugins.manager import PluginManager


class PluginHandler(base.SingleHandler):

    validator = plugin.PluginValidator
    single = objects.Plugin


class PluginCollectionHandler(base.CollectionHandler):

    collection = objects.PluginCollection
    validator = plugin.PluginValidator

    @content
    def POST(self):
        """:returns: JSONized REST object.
        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 409 (object with such parameters already exists)
        """
        data = self.checked_data(self.validator.validate)
        obj = self.collection.single.get_by_name_version(
            data['name'], data['version'])
        if obj:
            raise self.http(409, self.collection.single.to_json(obj))
        return super(PluginCollectionHandler, self).POST()


class PluginSyncHandler(base.BaseHandler):

    validator = plugin.PluginSyncValidator

    @content
    def POST(self):
        """:returns: JSONized REST object.
        :http: * 200 (plugins successfully synced)
               * 404 (plugin not found in db)
               * 400 (problem with parsing metadata file)
        """
        data = self.checked_data()
        ids = data.get('ids', None)

        try:
            PluginManager.sync_plugins_metadata(plugin_ids=ids)
        except errors.ParseError as exc:
            raise self.http(400, msg=six.text_type(exc))

        raise self.http(200, {})
