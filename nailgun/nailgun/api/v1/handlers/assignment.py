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
Handlers dealing with nodes assignment
"""

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import validate
from nailgun.api.v1.validators.assignment import NodeAssignmentValidator
from nailgun.api.v1.validators.assignment import NodeUnassignmentValidator

from nailgun import consts
from nailgun import objects


class NodeAssignmentHandler(BaseHandler):
    """Node assignment handler"""
    validator = NodeAssignmentValidator

    @handle_errors
    @validate
    def POST(self, cluster_id):
        """:returns: Empty string

        :http: * 200 (nodes are successfully assigned)
               * 400 (invalid nodes data specified)
               * 404 (cluster/node not found in db)
        """
        cluster = self.get_object_or_404(
            objects.Cluster,
            cluster_id
        )
        data = self.checked_data(
            self.validator.validate_collection_update,
            cluster_id=cluster.id
        )
        nodes = self.get_objects_list_or_404(
            objects.NodeCollection,
            data.keys()
        )

        for node in nodes:
            update = {"cluster_id": cluster.id, "pending_roles": data[node.id]}
            # NOTE(el): don't update pending_addition flag
            # if node is already assigned to the cluster
            # otherwise it would create problems for roles
            # update
            if not node.cluster:
                update["pending_addition"] = True
            objects.Node.update(node, update)

        # fuel-client expects valid json for all put and post request
        raise self.http(200, None)


class NodeUnassignmentHandler(BaseHandler):
    """Node assignment handler"""
    validator = NodeUnassignmentValidator

    @handle_errors
    @validate
    def POST(self, cluster_id):
        """:returns: Empty string

        :http: * 200 (node successfully unassigned)
               * 404 (cluster/node not found in db)
               * 400 (invalid data specified)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        nodes = self.checked_data(
            self.validator.validate_collection_update,
            cluster_id=cluster.id
        )
        for node in nodes:
            if node.status == consts.NODE_STATUSES.discover:
                objects.Node.remove_from_cluster(node)
                objects.Node.update(node, {"pending_addition": False})
            else:
                objects.Node.update(node, {"pending_deletion": True})

        raise self.http(200, None)
