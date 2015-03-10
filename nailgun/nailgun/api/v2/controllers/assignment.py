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

"""
Handlers dealing with nodes assignment
"""

import traceback

import pecan

from nailgun.api.v2.controllers.base import BaseController

from nailgun.api.v1.validators.assignment import NodeAssignmentValidator
from nailgun.api.v1.validators.assignment import NodeUnassignmentValidator

from nailgun import objects

from nailgun.logger import logger
from nailgun import notifier


class NodeAssignmentController(BaseController):
    """Node assignment controller
    """
    validator = NodeAssignmentValidator

    @pecan.expose(template='json:', content_type='application/json')
    def post(self, cluster_id):
        """:returns: Http response.
        :http: * 201 (nodes are successfully assigned)
               * 400 (invalid nodes data specified)
        """
        data = self.checked_data(
            self.validator.validate_collection_update,
            cluster_id=cluster_id
        )
        nodes = self.get_objects_list_or_404(objects.Node, data.keys())
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        for node in nodes:
            node.cluster = cluster
            node.pending_roles = data[node.id]
            node.pending_addition = True
            try:
                node.attributes.volumes = \
                    node.volume_manager.gen_volumes_info()

                objects.Cluster.add_pending_changes(
                    node.cluster,
                    "disks",
                    node_id=node.id
                )

                network_manager = objects.Node.get_network_manager(node)
                network_manager.assign_networks_by_default(node)
            except Exception as exc:
                logger.warning(traceback.format_exc())
                notifier.notify(
                    "error",
                    u"Failed to generate attributes for node '{0}': '{1}'"
                    .format(
                        node.human_readable_name(),
                        str(exc) or u"see logs for details"
                    ),
                    node_id=node.id
                )


class NodeUnassignmentController(BaseController):
    """Node assignment controller
    """
    validator = NodeUnassignmentValidator

    @pecan.expose(template='json:', content_type='application/json')
    def post(self, cluster_id):
        """:returns: Empty string
        :http: * 204 (node successfully unassigned)
               * 404 (node not found in db)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        nodes = self.checked_data(
            self.validator.validate_collection_update,
            cluster_id=cluster.id
        )
        for node in nodes:
            if node.status == "discover":
                objects.Cluster.clear_pending_changes(
                    node.cluster,
                    node_id=node.id
                )
                node.pending_roles = []
                node.cluster_id = None
                node.pending_addition = False
                objects.Node.get_network_manager(
                    node
                ).clear_assigned_networks(node)
            else:
                node.pending_deletion = True
