# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import pecan

from nailgun.api.v1.validators.node_group import NodeGroupValidator
from nailgun.api.v2.controllers.base import BaseController
from nailgun.db import db
from nailgun import objects


class NodeGroupController(BaseController):
    """NodeGroup collection handler
    """

    single = objects.NodeGroup
    collection = objects.NodeGroupCollection
    validator = NodeGroupValidator

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """May receive cluster_id parameter to filter list
        of groups

        :returns: Collection of JSONized Task objects.
        :http: * 200 (OK)
               * 404 (task not found in db)
        """
        user_data = pecan.request.GET

        if user_data.get('cluster_id') is not None:
            return self.collection.to_json(
                query=self.collection.get_by_cluster_id(
                    user_data.cluster_id
                )
            )
        else:
            return self.collection.to_json()

    @pecan.expose(template='json:', content_type='application/json')
    def delete(self, group_id):
        node_group = self.get_object_or_404(objects.NodeGroup, group_id)
        db().delete(node_group)
        db().commit()
        raise self.http(204)
