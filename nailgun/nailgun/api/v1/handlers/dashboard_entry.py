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
from nailgun.api.v1.validators import dashboard_entry
from nailgun.errors import errors
from nailgun import objects


class DashboardEntryHandler(base.SingleHandler):

    validator = dashboard_entry.DashboardEntryValidator
    single = objects.DashboardEntry

    def get_dashboard_entry_or_404(self, cluster_id, obj_id):
        d_e = self.single.get_by_release_id_role_name(release_id, role_name)
        if d_e is None:
            raise self.http(
                404,
                raise self.http(404, u'{0} not found'.format(d_e.__name__))
        return d_e

    @content
    def PUT(self, cluster_id, obj_id):
        """:returns: JSONized REST object.
        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        obj = self.get_dashboard_entry_or_404(self.single, cluster_id, obj_id)

        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )
        self.single.update(obj, data)
        return self.single.to_json(obj)


class DashboardEntryCollectionHandler(base.CollectionHandler):

    collection = objects.DashboardEntryCollection
    validator = dashboard_entry.DashboardEntryValidator

    @content
    def GET(self, cluster_id):
        """:returns: Collection of JSONized DashboardEntry objects.
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
        """
        data = self.checked_data()

        try:
            new_obj = self.collection.create_with_cluster_id(data, cluster_id)
        except errors.CannotCreate as exc:
            raise self.http(400, exc.message)
        raise self.http(201, self.collection.single.to_json(new_obj))
