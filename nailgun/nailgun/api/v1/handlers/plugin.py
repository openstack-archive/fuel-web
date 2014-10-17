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

from nailgun.api.v1.handlers import base
from nailgun import objects

from nailgun.api.v1.handlers.base import content_json


class PluginHandler(base.SingleHandler):

    single = objects.Plugin


class PluginCollectionHandler(base.CollectionHandler):

    collection = objects.PluginCollection


class PluginForClustersCollectionHandler(PluginCollectionHandler):

    @content_json
    def GET(self, cluster_id):
        """Filters list of plugins by cluster id parameter

        :returns: Collection of JSONized Plugin objects.
        :http: * 200 (OK)
        """
        query = self.collection.filter_by_cluster(cluster_id)
        return self.collection.to_json(query)


class ClusterPluginRelationHandler(base.SingleHandler):

    single = objects.ClusterPluginRelation

    def POST(self, cluster_id, plugin_id):
        plugin = self.get_object_or_404(objects.Plugin, plugin_id)
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.single.create(cluster, plugin)
        return self.http(201)

    def DELETE(self, cluster_id, plugin_id):
        plugin = self.get_object_or_404(objects.Plugin, plugin_id)
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self.single.delete(cluster, plugin)
        return self.http(204)
