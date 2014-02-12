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

import web

from nailgun.api.handlers.base import CollectionHandler
from nailgun.api.handlers.base import SingleHandler

from nailgun.api.handlers.base import content_json

from nailgun.objects import Task
from nailgun.objects import TaskCollection

"""
Handlers dealing with tasks
"""


class TaskHandler(SingleHandler):
    """Task single handler
    """

    single = Task


class TaskCollectionHandler(CollectionHandler):
    """Task collection handler
    """

    collection = TaskCollection

    @content_json
    def GET(self):
        """May receive cluster_id parameter to filter list
        of tasks

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
