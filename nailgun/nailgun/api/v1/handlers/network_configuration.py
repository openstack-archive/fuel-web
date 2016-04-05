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

"""
Handlers dealing with network configurations
"""

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content

from nailgun import objects


class NetworkAttributesDeployedHandler(BaseHandler):
    """Cluster deployed network attributes handler"""

    @content
    def GET(self, cluster_id):
        """:returns: JSONized deployed Cluster network configuration.

        :http: * 200 (OK)
               * 404 (cluster not found in db)
               * 404 (cluster does not have deployed configuration)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        attrs = objects.Transaction.get_network_settings(
            objects.TransactionCollection.get_last_succeed_run(cluster)
        )
        if not attrs:
            raise self.http(
                404, "Cluster does not have deployed configuration!"
            )
        return attrs
