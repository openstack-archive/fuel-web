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

from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import SingleHandler

from nailgun.api.v1.handlers.base import content_json
from nailgun.api.v1.validators.task import TaskValidator

from nailgun.errors import errors

from nailgun import objects


"""
Handlers dealing with tasks
"""


class TaskHandler(SingleHandler):
    """Task single handler
    """

    single = objects.Task
    validator = TaskValidator

    def DELETE(self, obj_id):
        """:returns: Empty string
        :http: * 204 (object successfully deleted)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(
            self.single,
            obj_id
        )

        force = web.input(force=None).force not in (None, u'', u'0')

        try:
            self.validator.validate_delete(obj, force)
        except errors.CannotDelete as exc:
            raise self.http(400, exc.message)

        self.single.delete(obj)
        raise self.http(204)


class TaskCollectionHandler(CollectionHandler):
    """Task collection handler
    """

    collection = objects.TaskCollection
    validator = TaskValidator

    @content_json
    def GET(self):
        """May receive cluster_id parameter to filter list
        of tasks

        :returns: Collection of JSONized Task objects.
        :http: * 200 (OK)
               * 404 (task not found in db)
        """
        cluster_id = web.input(cluster_id=None).cluster_id

        if cluster_id is not None:
            return self.collection.to_json(
                self.collection.get_by_cluster_id(cluster_id)
            )
        else:
            return self.collection.to_json()
