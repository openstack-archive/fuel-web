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
from nailgun.api.v1.validators import ip_address as ip_address
from nailgun import objects


class ClusterVIPHandler(base.SingleHandler):

    validator = ip_address.IPAddressValidator
    single = objects.IPAddress

    def GET(self, cluster_id, obj_id):
        """:returns: JSON-serialised IpAddress object.

        :http: * 200 (OK)
               * 404 (dashboard entry not found in db)
        """
        self.get_object_or_404(objects.Cluster, cluster_id)
        obj = self.get_object_or_404(self.single, obj_id)
        return self.single.to_json(obj)

    @content
    def PUT(self, cluster_id, obj_id):
        """:returns: JSON-serialised IpAddress object.

        :http: * 200 (OK)
               * 400 (invalid object data specified)
               * 404 (object not found in db)
        """
        self.get_object_or_404(objects.Cluster, cluster_id)
        obj = self.get_object_or_404(self.single, obj_id)

        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )
        self.single.update(obj, data)
        return self.single.to_json(obj)

    def PATCH(self, cluster_id, obj_id):
        """:returns: JSON-serialised IpAddress object.

        :http: * 200 (OK)
               * 400 (invalid object data specified)
               * 404 (object not found in db)
        """
        return self.PUT(cluster_id, obj_id)

    def DELETE(self, cluster_id):
        """Delete method disallowed

        :http: * 405 (method not supported)
        """
        raise self.http(405, 'Delete not supported for this entity')


class ClusterVIPCollectionHandler(base.CollectionHandler):

    collection = objects.IPAddressCollection
    validator = ip_address.IPAddressValidator

    @content
    def GET(self, cluster_id):
        """:returns: Collection of JSON-serialised IpAddress objects.

        :http: * 200 (OK)
               * 404 (cluster or ipaddr not found in db)
        """
        self.get_object_or_404(objects.Cluster, cluster_id)
        return self.collection.to_json(
            self.collection.get_by_cluster_id(cluster_id)
        )

    def POST(self, cluster_id):
        """Create method disallowed

        :http: * 405 (method not supported)
        """
        raise self.http(405, 'Create not supported for this entity')
