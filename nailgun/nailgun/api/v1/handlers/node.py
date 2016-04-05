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
Handlers dealing with nodes
"""

from datetime import datetime

import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.validators import node as node_validators

from nailgun import errors
from nailgun import objects

from nailgun.db import db

from nailgun.db.sqlalchemy.models import Node
from nailgun.task.manager import NodeDeletionTaskManager

from nailgun.logger import logger
from nailgun import notifier


class NodeHandler(SingleHandler):
    single = objects.Node
    validator = node_validators.NodeValidator

    @content
    def PUT(self, obj_id):
        """:returns: JSONized Node object.

        :http: * 200 (OK)
               * 400 (error occured while processing of data)
               * 404 (Node not found in db)
        """
        obj = self.get_object_or_404(self.single, obj_id)

        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )

        # NOTE(aroma):if node is being assigned to the cluster, and if network
        # template has been set for the cluster, network template will
        # also be applied to node; in such case relevant errors might
        # occur so they must be handled in order to form proper HTTP
        # response for user
        try:
            self.single.update(obj, data)
        except errors.NetworkTemplateCannotBeApplied as exc:
            raise self.http(400, exc.message)

        return self.single.to_json(obj)

    @content
    def DELETE(self, obj_id):
        """Deletes a node from DB and from Cobbler.

        :return: JSON-ed deletion task
        :http: * 200 (node has been succesfully deleted)
               * 202 (node is successfully scheduled for deletion)
               * 400 (data validation failed)
               * 404 (node not found in db)
               * 403 (on of the controllers is in error state)
        """

        node = self.get_object_or_404(self.single, obj_id)
        task_manager = NodeDeletionTaskManager(cluster_id=node.cluster_id)

        try:
            task = task_manager.execute([node], mclient_remove=False)
        except errors.ControllerInErrorState as e:
            raise self.http(403, e.message)

        self.raise_task(task)


class NodeCollectionHandler(CollectionHandler):
    """Node collection handler"""

    validator = node_validators.NodeValidator
    collection = objects.NodeCollection

    @content
    def GET(self):
        """May receive cluster_id parameter to filter list of nodes

        :returns: Collection of JSONized Node objects.
        :http: * 200 (OK)
        """
        cluster_id = web.input(cluster_id=None).cluster_id
        nodes = self.collection.eager_nodes_handlers(None)

        if cluster_id == '':
            nodes = nodes.filter_by(cluster_id=None)
        elif cluster_id:
            nodes = nodes.filter_by(cluster_id=cluster_id)

        return self.collection.to_json(nodes)

    @content
    def PUT(self):
        """:returns: Collection of JSONized Node objects.

        :http: * 200 (nodes are successfully updated)
               * 400 (data validation failed)
        """
        data = self.checked_data(
            self.validator.validate_collection_update
        )

        nodes_updated = []
        for nd in data:
            node = self.collection.single.get_by_meta(nd)

            if not node:
                raise self.http(404, "Can't find node: {0}".format(nd))

            try:
                self.collection.single.update(node, nd)
            except errors.NetworkTemplateCannotBeApplied as exc:
                raise self.http(400, exc.message)

            nodes_updated.append(node.id)

        # we need eagerload everything that is used in render
        nodes = self.collection.filter_by_id_list(
            self.collection.eager_nodes_handlers(None),
            nodes_updated
        )
        return self.collection.to_json(nodes)

    @content
    def DELETE(self):
        """Deletes a batch of nodes.

        Takes (JSONed) list of node ids to delete.

        :return: JSON-ed deletion task
        :http: * 200 (nodes have been succesfully deleted)
               * 202 (nodes are successfully scheduled for deletion)
               * 400 (data validation failed)
               * 404 (nodes not found in db)
               * 403 (on of the controllers is in error state)
        """
        # TODO(pkaminski): web.py does not support parsing of array arguments
        # in the queryset so we specify the input as comma-separated list
        node_ids = self.checked_data(
            validate_method=self.validator.validate_collection_delete,
            data=web.input().get('ids', '')
        )

        nodes = self.get_objects_list_or_404(self.collection, node_ids)

        task_manager = NodeDeletionTaskManager(cluster_id=nodes[0].cluster_id)

        # NOTE(aroma): ditto as in comments for NodeHandler's PUT method;
        try:
            task = task_manager.execute(nodes, mclient_remove=False)
        except errors.ControllerInErrorState as e:
            raise self.http(403, e.message)

        self.raise_task(task)


class NodeAgentHandler(BaseHandler):

    collection = objects.NodeCollection
    validator = node_validators.NodeValidator

    @content
    def PUT(self):
        """:returns: node id.

        :http: * 200 (node are successfully updated)
               * 304 (node data not changed since last request)
               * 400 (data validation failed)
               * 404 (node not found)
        """
        nd = self.checked_data(
            self.validator.validate_update,
            data=web.data())

        node = self.collection.single.get_by_meta(nd)

        if not node:
            raise self.http(404, "Can't find node: {0}".format(nd))

        node.timestamp = datetime.now()

        if not node.online:
            node.online = True
            msg = u"Node '{0}' is back online".format(node.human_readable_name)
            logger.info(msg)
            notifier.notify("discover", msg, node_id=node.id)
        db().flush()

        if 'agent_checksum' in nd and (
            node.agent_checksum == nd['agent_checksum']
        ):
            return {'id': node.id, 'cached': True}

        self.collection.single.update_by_agent(node, nd)
        return {"id": node.id}


class NodesAllocationStatsHandler(BaseHandler):
    """Node allocation stats handler"""

    @content
    def GET(self):
        """:returns: Total and unallocated nodes count.

        :http: * 200 (OK)
        """
        unallocated_nodes = db().query(Node).filter_by(cluster_id=None).count()
        total_nodes = \
            db().query(Node).count()
        return {'total': total_nodes,
                'unallocated': unallocated_nodes}


class NodeAttributesHandler(BaseHandler):
    """Node attributes handler"""

    validator = node_validators.NodeAttributesValidator

    @content
    def GET(self, node_id):
        """:returns: JSONized Node attributes.

        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)

        return objects.Node.get_attributes(node)

    @content
    def PUT(self, node_id):
        """:returns: JSONized Node attributes.

        :http: * 200 (OK)
               * 400 (wrong attributes data specified)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)

        if not node.cluster:
            raise self.http(400, "Node '{}' doesn't belong to any cluster"
                            .format(node.id))

        data = self.checked_data(node=node, cluster=node.cluster)
        objects.Node.update_attributes(node, data)

        return objects.Node.get_attributes(node)
