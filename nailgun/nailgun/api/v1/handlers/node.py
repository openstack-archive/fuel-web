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
from nailgun.api.v1.validators.network import NetAssignmentValidator
from nailgun.api.v1.validators.node import NodeValidator

from nailgun import consts
from nailgun.errors import errors
from nailgun import objects

from nailgun.objects.serializers.node import NodeInterfacesSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import NodeNICInterface

from nailgun.task.manager import NodeDeletionTaskManager

from nailgun.logger import logger
from nailgun import notifier


class NodeHandler(SingleHandler):
    single = objects.Node
    validator = NodeValidator

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

    validator = NodeValidator
    collection = objects.NodeCollection

    @content
    def GET(self):
        """May receive cluster_id parameter to filter list of nodes

        :returns: Collection of JSONized Node objects.
        :http: * 200 (OK)
        """

        data = self.read_and_validate_input_data()

        nodes = self.collection.eager_nodes_handlers(None)
        if 'roles' in data:
            nodes = self.collection.filter_by_roles(nodes, data.pop('roles'))

        nodes = self.collection.filter_by(nodes, **data)

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

            self.collection.single.update(node, nd)
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

        try:
            task = task_manager.execute(nodes, mclient_remove=False)
        except errors.ControllerInErrorState as e:
            raise self.http(403, e.message)

        self.raise_task(task)

    def read_and_validate_input_data(self):
        """Read and validate input data.

        Retrieve and validate input data from a request.

        :return: dict - validated data
        """

        data = {}
        input_data = web.input(roles=[])

        for param in ('cluster_id', 'group_id', ):
            value = input_data.get(param)
            if value == '':
                data[param] = None
            elif value:
                try:
                    data[param] = int(value)
                except ValueError:
                    msg = 'Invalid \'{0}\' value: {1}'.format(param, value)
                    logger.debug(msg)
                    raise self.http(400, msg)

        roles = input_data.get('roles')
        if roles:
            data['roles'] = roles

        status = input_data.get('status')
        if status:
            if status in consts.NODE_STATUSES:
                data['status'] = status
            else:
                msg = 'Invalid \'status\' value: {0}'.format(status)
                logger.debug(msg)
                raise self.http(400, msg)

        if 'online' in input_data:
            value = input_data.get('online')
            if value.lower() in ('1', 'true', ):
                data['online'] = True
            elif value.lower() in ('0', 'false', ):
                data['online'] = False
            else:
                msg = 'Invalid \'online\' value: {0}'.format(value)
                logger.debug(msg)
                raise self.http(400, msg)

        return data


class NodeAgentHandler(BaseHandler):

    collection = objects.NodeCollection
    validator = NodeValidator

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


class NodeNICsHandler(BaseHandler):
    """Node network interfaces handler"""

    model = NodeNICInterface
    validator = NetAssignmentValidator
    serializer = NodeInterfacesSerializer

    @content
    def GET(self, node_id):
        """:returns: Collection of JSONized Node interfaces.

        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)
        return map(self.render, node.interfaces)

    @content
    def PUT(self, node_id):
        """:returns: Collection of JSONized Node objects.

        :http: * 200 (nodes are successfully updated)
               * 400 (data validation failed)
        """
        interfaces_data = self.checked_data(
            self.validator.validate_structure_and_data, node_id=node_id)
        node_data = {'id': node_id, 'interfaces': interfaces_data}

        objects.Cluster.get_network_manager()._update_attrs(node_data)
        node = self.get_object_or_404(objects.Node, node_id)
        objects.Node.add_pending_change(
            node,
            consts.CLUSTER_CHANGES.interfaces
        )
        return map(self.render, node.interfaces)


class NodeCollectionNICsHandler(BaseHandler):
    """Node collection network interfaces handler"""

    model = NetworkGroup
    validator = NetAssignmentValidator
    serializer = NodeInterfacesSerializer

    @content
    def PUT(self):
        """:returns: Collection of JSONized Node objects.

        :http: * 200 (nodes are successfully updated)
               * 400 (data validation failed)
        """
        data = self.checked_data(
            self.validator.validate_collection_structure_and_data)
        updated_nodes_ids = []
        for node_data in data:
            node_id = objects.Cluster.get_network_manager()._update_attrs(
                node_data)
            updated_nodes_ids.append(node_id)
        updated_nodes = db().query(Node).filter(
            Node.id.in_(updated_nodes_ids)
        ).all()
        return [
            {
                "id": n.id,
                "interfaces": map(self.render, n.interfaces)
            } for n in updated_nodes
        ]


class NodeNICsDefaultHandler(BaseHandler):
    """Node default network interfaces handler"""

    @content
    def GET(self, node_id):
        """:returns: Collection of default JSONized interfaces for node.

        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)
        return self.get_default(node)

    def get_default(self, node):
        if node.cluster:
            return objects.Cluster.get_network_manager(
                node.cluster
            ).get_default_interfaces_configuration(node)


class NodeCollectionNICsDefaultHandler(NodeNICsDefaultHandler):
    """Node collection default network interfaces handler"""

    validator = NetAssignmentValidator

    @content
    def GET(self):
        """May receive cluster_id parameter to filter list of nodes

        :returns: Collection of JSONized Nodes interfaces.
        :http: * 200 (OK)
        """
        cluster_id = web.input(cluster_id=None).cluster_id

        if cluster_id:
            nodes = \
                objects.NodeCollection.filter_by(None, cluster_id=cluster_id)
        else:
            nodes = objects.NodeCollection.all()

        return filter(lambda x: x is not None, map(self.get_default, nodes))


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
