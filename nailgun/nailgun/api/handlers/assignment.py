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

import traceback

import web

from nailgun.api.handlers.base import BaseHandler
from nailgun.api.handlers.base import content_json
from nailgun.api.validators.assignment import NodeAssignmentValidator
from nailgun.api.validators.assignment import NodeUnassignmentValidator
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.logger import logger
from nailgun.network.manager import NetworkManager
from nailgun import notifier


class NodeAssignmentHandler(BaseHandler):
    """Node assignment handler
    """
    validator = NodeAssignmentValidator

    @content_json
    def POST(self):
        """:returns: Http response.
        :http: * 201 (nodes are successfully assigned)
               * 400 (invalid nodes data specified)
        """
        data = self.checked_data(self.validator.validate_collection_update)
        nodes = self.get_objects_list_or_404(Node, data["assignment"].keys())
        cluster = self.get_object_or_404(Cluster, data["cluster_id"])
        for node in nodes:
            if node.cluster:
                raise web.webapi.BadRequest(
                    "Node must be unassigned before it can be assigned again."
                )
            node.cluster_id = cluster.id
            node.cluster = cluster
            node.pending_roles = data["assignment"][str(node.id)]
            node.pending_addition = True
            try:
                node.attributes.volumes = \
                    node.volume_manager.gen_volumes_info()
                node.cluster.add_pending_changes(
                    "disks",
                    node_id=node.id
                )
            except Exception as exc:
                msg = (
                    u"Failed to generate volumes info for node '{0}': '{1}'"
                ).format(
                    node.name or data.get("mac") or data.get("id"),
                    str(exc) or u"see logs for details"
                )
                logger.warning(traceback.format_exc())
                notifier.notify("error", msg, node_id=node.id)
            db().commit()
            network_manager = node.cluster.network_manager
            network_manager.assign_networks_by_default(node)
        raise web.webapi.created("{}")


class NodeUnassignmentHandler(BaseHandler):
    """Node assignment handler
    """
    validator = NodeUnassignmentValidator

    @content_json
    def POST(self):
        """:returns: Empty string
        :http: * 204 (node successfully unassigned)
               * 404 (node not found in db)
        """
        data = self.checked_data(self.validator.validate_collection_update)
        nodes = self.get_objects_list_or_404(Node, data)
        for node in nodes:
            if not node.cluster:
                raise web.BadRequest("Can't unassign node if it not assigned.")
            if node.status == "discover":
                node.cluster_id = None
                node.pending_roles = []
                node.pending_addition = False
                node.cluster.clear_pending_changes(node_id=node.id)
                NetworkManager.clear_assigned_networks(node)
            else:
                node.pending_deletion = True
            db().commit()
        raise web.webapi.HTTPError(
            status="202 Accepted",
            data=""
        )
