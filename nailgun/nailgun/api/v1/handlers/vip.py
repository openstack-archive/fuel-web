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
from oslo_serialization import jsonutils


class ClusterVIPHandler(base.SingleHandler):

    validator = ip_address.IPAddressValidator
    single = objects.IPAddress

    def _get_vip_from_cluster_or_http_error(self, cluster_id, ip_address_id):
        obj = self.get_object_or_404(self.single, ip_address_id)
        if not int(cluster_id) == obj.network_data.nodegroup.cluster_id:
            raise self.http(
                404,
                "Cluster with (ID={0}) not found".format(cluster_id)
            )
        elif not obj.vip_info:
            raise self.http(
                400,
                "Ip address with (ID={0}) exist but have no "
                "VIP metadata attached".format(ip_address_id)
            )
        else:
            return obj

    def GET(self, cluster_id, ip_address_id):
        """:returns: JSON-serialised IpAddress object.

        :http: * 200 (OK)
               * 400 (ip_address entry contains no VIP metadata)
               * 404 (ip_address entry not found in db)
        """
        obj = self._get_vip_from_cluster_or_http_error(
            cluster_id, ip_address_id)
        return self.single.to_json(obj)

    @content
    def PUT(self, cluster_id, ip_address_id):
        """:returns: JSON-serialised IpAddress object.

        :http: * 200 (OK)
               * 400 (ip_address entry contains no VIP metadata)
               * 404 (ip_address entry not found in db)
        """
        obj = self._get_vip_from_cluster_or_http_error(
            cluster_id, ip_address_id)

        data = self.checked_data()
        self.single.update(obj, data)
        return self.single.to_json(obj)

    def PATCH(self, cluster_id, ip_address_id):
        """:returns: JSON-serialised IpAddress object.

        :http: * 200 (OK)
               * 400 (ip_address entry contains no VIP metadata)
               * 404 (ip_address entry not found in db)
        """
        return self.PUT(cluster_id, ip_address_id)

    def DELETE(self, cluster_id, ip_address_id):
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
               * 404 (cluster not found in db)
        """
        self.get_object_or_404(objects.Cluster, cluster_id)
        return self.collection.to_json(
            self.collection.get_vips_by_cluster_id(cluster_id)
        )

    def POST(self, cluster_id):
        """Create method disallowed.

        :http: * 405 (method not supported)
        """
        raise self.http(405, 'Create not supported for this entity')

    @content
    def PUT(self, cluster_id):
        """:returns: Collection of JSON-serialised updated IpAddress objects.

        :http: * 200 (OK)
               * 400 (some ip_address ids not found or data validation failed)
        """
        vips_to_update = self.checked_data()

        existing_vips = self.collection.get_vips_by_cluster_id(cluster_id)
        existing_vips_id = set(vip.id for vip in existing_vips)

        records_with_no_id = [
            vip for vip in vips_to_update if not vip.get('id')]
        if records_with_no_id:
            raise self.http(
                400,
                "{0} record{1} have no 'id' field:\n{2}".format(
                    len(records_with_no_id),
                    "s" if len(records_with_no_id) > 1 else "",
                    "\n".join(jsonutils.dumps(r) for r in records_with_no_id)
                )
            )

        not_found_id = [
            vip.get('id') for vip in vips_to_update
            if vip.get('id') not in existing_vips_id]
        if not_found_id:
            raise self.http(
                400,
                "IP address{0} with id{1} {2} not found in "
                "cluster (ID={3})".format(
                    "es" if len(not_found_id) > 1 else "",
                    "s" if len(not_found_id) > 1 else "",
                    not_found_id,
                    cluster_id
                )
            )
        return self.collection.to_json(
            self.collection.update(vips_to_update)
        )

    def PATCH(self, cluster_id):
        """:returns: Collection of JSON-serialised updated IpAddress objects.

        :http: * 200 (OK)
               * 400 (some ip_address ids not found or data validation failed)
        """
        return self.PUT(cluster_id)
