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

import pecan

from nailgun.api.v2.controllers.base import BaseController

from nailgun.api.v1.validators.task import TaskValidator

from nailgun.errors import errors

from nailgun import objects


"""
Controllers dealing with tasks
"""


class TaskController(BaseController):
    """Task single handler
    """

    single = objects.Task
    collection = objects.TaskCollection
    validator = TaskValidator

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """May receive cluster_id parameter to filter list
        of tasks

        :returns: Collection of JSONized Task objects.
        :http: * 200 (OK)
               * 404 (task not found in db)
        """
        request = pecan.request
        cluster_id = request.params.get("cluster_id", None)

        if cluster_id is not None:
            return self.collection.to_json(
                self.collection.get_by_cluster_id(cluster_id)
            )
        else:
            return self.collection.to_json()

    @pecan.expose(template='json:', content_type='application/json')
    def delete_one(self, obj_id):
        """:returns: Empty string
        :http: * 204 (object successfully deleted)
               * 404 (object not found in db)
        """
        request = pecan.request
        obj = self.get_object_or_404(
            self.single.model,
            obj_id
        )

        force = request.params.get("force", None) not in (None, u'', u'0')

        try:
            self.validator.validate_delete(obj, force)
        except errors.CannotDelete as exc:
            raise self.http(400, exc.message)

        self.single.delete(obj)
        raise self.http(204, 'No Content')
