# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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


from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.validators.deployment_graph import DeploymentGraphValidator
from nailgun import consts
from nailgun import objects
from nailgun.objects.serializers.deployment_graph import \
    DeploymentGraphSerializer


class LinkedDeploymentGraphHandler(SingleHandler):
    """Handler for deployment graph linked to model."""

    validator = DeploymentGraphValidator
    serializer = DeploymentGraphSerializer

    @content
    def GET(self, obj_id, graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE):
        """Get deployment graph.

        :param obj_id: linked model ID
        :type obj_id: int|basestring
        :param graph_type: deployment graph type, default is 'default'
        :type graph_type: basestring

        :returns: Deployment graph
        :rtype: dict

        :http: * 200 OK
               * 400 (no graph of such type)
               * 404 (release object not found)
        """
        obj = self.get_object_or_404(self.single, int(obj_id))
        deployment_graph = objects.DeploymentGraph.get_for_model(
            obj, graph_type)
        if deployment_graph:
            return objects.DeploymentGraph.to_json(deployment_graph)
        else:
            raise self.http(404, "Graph with type: {0} is not defined".format(
                graph_type))

    @content
    def PUT(self, obj_id, graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE):
        """Update deployment graph.

        :param obj_id: linked model ID
        :type obj_id: int|basestring
        :param graph_type: deployment graph type, default is 'default'
        :type graph_type: basestring

        :returns:  Deployment graph data
        :rtype: dict

        :http: * 200 (OK)
               * 400 (invalid data specified)
               * 404 (object not found in db)

        """
        obj = self.get_object_or_404(self.single, int(obj_id))
        data = self.checked_data()
        deployment_graph = objects.DeploymentGraph.upsert_for_model(
            data, obj, graph_type)
        return objects.DeploymentGraph.to_json(deployment_graph)

    @content
    def PATCH(self, obj_id, graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE):
        """Update deployment graph.

        :param obj_id: linked model ID
        :type obj_id: int|basestring
        :param graph_type: deployment graph type, default is 'default'
        :type graph_type: basestring

        :returns:  Deployment graph data
        :rtype: dict

        :http: * 200 (OK)
               * 400 (invalid data specified)
               * 404 (object not found in db)
        """
        return self.PUT(obj_id, graph_type)

    def DELETE(self, obj_id, graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE):
        """Delete deployment graph.

        :param obj_id: linked model ID
        :type obj_id: int|basestring
        :param graph_type: deployment graph type, default is 'default'
        :type graph_type: basestring

        :http: * 204 (OK)
               * 404 (object not found in db)
        """

        obj = self.get_object_or_404(self.single, int(obj_id))
        deployment_graph = objects.DeploymentGraph.get_for_model(
            obj, graph_type)
        if deployment_graph:
            objects.DeploymentGraph.delete(deployment_graph)
        # no graph not raising anything


class LinkedDeploymentGraphCollectionHandler(CollectionHandler):
    """Handler for deployment graphs linked to models collection."""

    validator = DeploymentGraphValidator
    single = None   # single will be substituted during handler inheritance
    collection = objects.DeploymentGraphCollection

    @content
    def GET(self, obj_id):
        """

        :param obj_id: related model object ID
        :type obj_id: int|basestring

        :returns: JSONized object.

        :http: * 200 (OK)
               * 400 (invalid object data specified)
               * 404 (object not found in db)
        """
        related_model = self.get_object_or_404(self.single, int(obj_id))
        graphs = self.collection.get_for_model(related_model)
        return self.collection.to_json(graphs)


class DeploymentGraphHandler(SingleHandler):
    """Handler for fetching and deletion of the deployment graph."""

    validator = DeploymentGraphValidator
    single = objects.DeploymentGraph

    @content
    def DELETE(self, obj_id):
        """:http: * 204 (OK)
               * 404 (object not found in db)
        """
        d_e = self.get_object_or_404(self.single, obj_id)
        self.single.delete(d_e)
        raise self.http(204)


class DeploymentGraphCollectionHandler(CollectionHandler):
    """Handler for deployment graphs collection."""
    collection = objects.DeploymentGraphCollection
