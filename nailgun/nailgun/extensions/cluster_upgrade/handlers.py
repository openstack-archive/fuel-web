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
from nailgun import objects

from . import validators
from .objects import adapters


class ClusterUpgradeHandler(base.BaseHandler):
    single = objects.Cluster
    validator = validators.ClusterUpgradeValidator

    @base.content
    def POST(self, cluster_id):
        """Initialize the upgrade of the cluster.

        Creates a new cluster with specified name and release_id. The
        new cluster is created with parameters that are copied from the
        cluster with the given cluster_id. The values of the generated
        and editable attributes are just copied from one to the other.

        :param cluster_id: ID of the cluster from which parameters would
                           be copied
        :returns: JSON representation of the created cluster
        :http: * 200 (OK)
               * 400 (upgrade parameters are invalid)
               * 404 (node or release not found in db)
        """
        from . import upgrade

        orig_cluster = adapters.NailgunClusterAdapter(
            self.get_object_or_404(self.single, cluster_id))
        request_data = self.checked_data(cluster=orig_cluster)
        new_cluster = upgrade.UpgradeHelper.clone_cluster(orig_cluster,
                                                          request_data)
        return new_cluster.to_json()
