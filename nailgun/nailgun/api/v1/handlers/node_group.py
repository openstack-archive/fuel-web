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

"""
Handlers dealing with node groups
"""

import web

from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.handlers.decorators import handle_errors
from nailgun.api.v1.handlers.decorators import validate
from nailgun.api.v1.validators.node_group import NodeGroupValidator

from nailgun import errors
from nailgun import objects


class NodeGroupHandler(SingleHandler):
    """NodeGroup single handler"""
    single = objects.NodeGroup
    validator = NodeGroupValidator

    @handle_errors
    @validate
    def DELETE(self, group_id):
        """:returns: {}

        :http: * 204 (object successfully deleted)
               * 400 (data validation or some of tasks failed)
               * 404 (nodegroup not found in db)
               * 409 (previous dsnmasq setup is not finished yet)
        """
        node_group = self.get_object_or_404(objects.NodeGroup, group_id)

        self.checked_data(
            self.validator.validate_delete,
            instance=node_group
        )

        try:
            self.single.delete(node_group)
        except errors.TaskAlreadyRunning as exc:
            raise self.http(409, exc.message)
        except Exception as exc:
            raise self.http(400, exc.message)

        raise self.http(204)


class NodeGroupCollectionHandler(CollectionHandler):
    """NodeGroup collection handler"""

    collection = objects.NodeGroupCollection
    validator = NodeGroupValidator

    @handle_errors
    @validate
    def GET(self):
        """May receive cluster_id parameter to filter list of groups

        :returns: Collection of JSONized Task objects.
        :http: * 200 (OK)
               * 404 (task not found in db)
        """
        user_data = web.input(cluster_id=None)

        if user_data.cluster_id is not None:
            return self.collection.to_list(
                self.collection.get_by_cluster_id(
                    user_data.cluster_id
                )
            )
        else:
            return self.collection.to_list()
