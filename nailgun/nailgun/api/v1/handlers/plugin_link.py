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

from nailgun.api.v1.handlers import base
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.validators import plugin_link
from nailgun.errors import errors
from nailgun import objects


class PluginLinkHandler(base.SingleHandler):

    validator = plugin_link.PluginLinkValidator
    single = objects.PluginLink

    def _get_plugin_link_object(self, plugin_id, obj_id):
        obj = self.get_object_or_404(self.single, obj_id)
        if int(plugin_id) == obj.plugin_id:
            return obj
        else:
            raise self.http(
                404,
                "Plugin with id {0} not found".format(plugin_id)
            )

    def GET(self, plugin_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 404 (dashboard entry not found in db)
        """
        obj = self._get_plugin_link_object(plugin_id, obj_id)
        return self.single.to_json(obj)

    @content
    def PUT(self, plugin_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 400 (invalid object data specified)
               * 404 (object not found in db)
        """
        obj = self._get_plugin_link_object(plugin_id, obj_id)
        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )
        self.single.update(obj, data)
        return self.single.to_json(obj)

    def PATCH(self, plugin_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 400 (invalid object data specified)
               * 404 (object not found in db)
        """
        return self.PUT(plugin_id, obj_id)

    @content
    def DELETE(self, plugin_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 204 (OK)
               * 404 (object not found in db)
        """
        obj = self._get_plugin_link_object(plugin_id, obj_id)
        self.single.delete(obj)
        raise self.http(204)


class PluginLinkCollectionHandler(base.CollectionHandler):

    collection = objects.PluginLinkCollection
    validator = plugin_link.PluginLinkValidator

    @content
    def GET(self, plugin_id):
        """:returns: Collection of JSONized PluginLink objects.

        :http: * 200 (OK)
               * 404 (plugin not found in db)
        """
        self.get_object_or_404(objects.Plugin, plugin_id)
        return self.collection.to_json(
            self.collection.order_by(
                self.collection.get_by_plugin_id(plugin_id)))

    @content
    def POST(self, plugin_id):
        """:returns: JSONized REST object.

        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
        """
        data = self.checked_data()

        try:
            new_obj = self.collection.create_with_plugin_id(data, plugin_id)
        except errors.CannotCreate as exc:
            raise self.http(400, exc.message)
        raise self.http(201, self.collection.single.to_json(new_obj))
