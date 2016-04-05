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

import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content
from nailgun.extensions.network_manager.validators.network import \
    NetAssignmentValidator

from nailgun import consts
from nailgun import objects

from nailgun.extensions.network_manager.objects.serializers.nic import \
    NodeInterfacesSerializer

from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import NodeNICInterface


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
        updated_nodes = objects.NodeCollection.filter_by_id_list(
            None, updated_nodes_ids
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
