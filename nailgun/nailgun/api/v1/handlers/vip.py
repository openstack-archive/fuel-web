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


import web

from nailgun.api.v1.handlers import base
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.validators import ip_addr
from nailgun import objects


class ClusterVIPHandler(base.SingleHandler):

    validator = ip_addr.IPAddrValidator
    single = objects.IPAddr

    def _get_vip_from_cluster_or_http_error(self, cluster_id, ip_addr_id):
        obj = self.get_object_or_404(self.single, ip_addr_id)
        if not int(cluster_id) == obj.network_data.nodegroup.cluster_id:
            raise self.http(
                404,
                "IP address with (ID={0}) does not belong to "
                "cluster (ID={1})".format(ip_addr_id, cluster_id)
            )
        elif not obj.vip_name:
            raise self.http(
                400,
                "IP address with (ID={0}) exists but has no "
                "VIP metadata attached".format(ip_addr_id)
            )
        else:
            return obj

    def GET(self, cluster_id, ip_addr_id):
        """:returns: JSON-serialised IpAddr object.

        :http: * 200 (OK)
               * 400 (data validation failed)
               * 404 (ip_addr entry not found in db)
        """
        obj = self._get_vip_from_cluster_or_http_error(
            cluster_id, ip_addr_id)
        return self.single.to_json(obj)

    @content
    def PUT(self, cluster_id, ip_addr_id):
        """:returns: JSON-serialised IpAddr object.

        :http: * 200 (OK)
               * 400 (data validation failed)
               * 404 (ip_addr entry not found in db)
        """
        obj = self._get_vip_from_cluster_or_http_error(
            cluster_id, ip_addr_id)

        data = self.checked_data()
        self.single.update(obj, data)
        return self.single.to_json(obj)

    def PATCH(self, cluster_id, ip_addr_id):
        """:returns: JSON-serialised IpAddr object.

        :http: * 200 (OK)
               * 400 (data validation failed)
               * 404 (ip_addr entry not found in db)
        """
        return self.PUT(cluster_id, ip_addr_id)

    def DELETE(self, cluster_id, ip_addr_id):
        """Delete method disallowed

        :http: * 405 (method not supported)
        """
        raise self.http(405, 'Delete is not supported for this entity')


class ClusterVIPCollectionHandler(base.CollectionHandler):

    collection = objects.IPAddrCollection
    validator = ip_addr.IPAddrValidator

    @content
    def GET(self, cluster_id):
        """:returns: Collection of JSON-serialised IpAddr objects.

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        network_id = web.input(network_id=None).network_id
        network_role = web.input(network_role=None).network_role

        self.get_object_or_404(objects.Cluster, cluster_id)
        return self.collection.to_json(
            self.collection.get_vips_by_cluster_id(
                    cluster_id, network_id, network_role)
        )

    def POST(self, cluster_id):
        """Create method disallowed.

        :http: * 405 (method not supported)
        """
        raise self.http(405, 'Create is not supported for this entity')

    @content
    def PUT(self, cluster_id):
        """:returns: Collection of JSON-serialised updated IpAddr objects.

        :http: * 200 (OK)
               * 400 (data validation failed)
        """
        update_data = self.checked_data(
            self.validator.validate_collection_update,
            cluster_id=cluster_id
        )

        return self.collection.to_json(
            self.collection.update_vips(update_data)
        )

    def PATCH(self, cluster_id):
        """:returns: Collection of JSON-serialised updated IpAddr objects.

        :http: * 200 (OK)
               * 400 (data validation failed)
        """
        return self.PUT(cluster_id)
