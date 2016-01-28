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

import sqlalchemy as sa

from nailgun.api.v1.handlers import base
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.validators import plugin_link
from nailgun.errors import errors
from nailgun import objects


class ClusterPluginLinkHandler(base.SingleHandler):

    validator = plugin_link.PluginLinkValidator
    single = objects.ClusterPluginLink

    def GET(self, cluster_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 404 (dashboard entry not found in db)
        """
        self.get_object_or_404(objects.Cluster, cluster_id)

        obj = self.get_object_or_404(self.single, obj_id)
        return self.single.to_json(obj)

    @content
    def PUT(self, cluster_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 400 (invalid object data specified)
               * 404 (object not found in db)
               * 409 (url field duplicate conflict)
        """
        obj = self.get_object_or_404(self.single, obj_id)
        data = self.checked_data(
            self.validator.validate_update,
            instance=obj,
            model=self.single.model
        )
        # try:
        try:
            self.single.update(obj, data)
        except sa.exc.IntegrityError as exc:
            raise self.http(409, exc.message)
        return self.single.to_json(obj)

    def PATCH(self, cluster_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 400 (invalid object data specified)
               * 404 (object not found in db)
               * 409 (url field duplicate conflict)
        """
        return self.PUT(cluster_id, obj_id)

    @content
    def DELETE(self, cluster_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 204 (OK)
               * 404 (object not found in db)
        """
        d_e = self.get_object_or_404(self.single, obj_id)
        self.single.delete(d_e)
        raise self.http(204)


class ClusterPluginLinkCollectionHandler(base.CollectionHandler):

    collection = objects.ClusterPluginLinkCollection
    validator = plugin_link.PluginLinkValidator

    @content
    def GET(self, cluster_id):
        """:returns: Collection of JSONized ClusterPluginLink objects.

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        self.get_object_or_404(objects.Cluster, cluster_id)
        return self.collection.to_json(
            self.collection.get_by_cluster_id(cluster_id)
        )

    @content
    def POST(self, cluster_id):
        """:returns: JSONized REST object.

        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 409 (url field duplicate conflict)
        """
        data = self.checked_data(
            model=self.collection.single.model
        )

        try:
            new_obj = self.collection.create_with_cluster_id(data, cluster_id)
        except errors.CannotCreate as exc:
            raise self.http(400, exc.message)
        except sa.exc.IntegrityError as exc:
            raise self.http(409, exc.message)
        raise self.http(201, self.collection.single.to_json(new_obj))
