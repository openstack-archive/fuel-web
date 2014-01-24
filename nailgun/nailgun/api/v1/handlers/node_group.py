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

import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import SingleHandler

from nailgun.api.v1.handlers.base import content_json
from nailgun.api.v1.validators.node_group import NodeGroupValidator

from nailgun.db import db

from nailgun import objects

"""
Handlers dealing with node groups
"""


class NodeGroupHandler(SingleHandler):
    """NodeGroup single handler
    """
    single = objects.NodeGroup
    validator = NodeGroupValidator

    def DELETE(self, group_id):
        node_group = self.get_object_or_404(objects.NodeGroup, group_id)
        db().delete(node_group)
        db().commit()
        raise web.webapi.HTTPError(
            status="204 No Content",
            data=""
        )


class NodeGroupCollectionHandler(CollectionHandler):
    """NodeGroup collection handler
    """

    collection = objects.NodeGroupCollection
    validator = NodeGroupValidator

    @content_json
    def GET(self):
        """May receive cluster_id parameter to filter list
        of groups

        :returns: Collection of JSONized Task objects.
        :http: * 200 (OK)
               * 404 (task not found in db)
        """
        user_data = web.input(cluster_id=None)

        if user_data.cluster_id is not None:
            return self.collection.to_json(
                query=self.collection.get_by_cluster_id(
                    user_data.cluster_id
                )
            )
        else:
            return self.collection.to_json()


class NodeGroupAssignmentHandler(BaseHandler):
    """Node group assignment handler
    """

    @content_json
    def POST(self, group_id):
        """:returns: Http response.
        :http: * 201 (nodes are successfully assigned)
               * 400 (invalid nodes data specified)
        """
        self.get_object_or_404(
            objects.NodeGroup,
            group_id
        )
        data = self.checked_data()

        nodes = self.get_objects_list_or_404(
            objects.NodeCollection,
            data
        )

        for node in nodes:
            objects.Node.update(node, {"group_id": group_id})
