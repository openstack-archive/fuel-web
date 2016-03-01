# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

from nailgun.api.v1.handlers import base
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.validators import tasks_history
from nailgun.errors import errors
from nailgun import objects


class TasksHistoryHandler(base.SingleHandler):

    validator = tasks_history.TasksHistoryValidator
    single = objects.TasksHistory

    def GET(self, cluster_id, obj_id):
        self.get_object_or_404(objects.Task, task_deployment_id)

        obj = self.get_object_or_404(self.single, obj_id)
        return self.single.to_json(obj)

    @content
    def PUT(self, cluster_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(self.single, obj_id)

        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )
        self.single.update(obj, data)
        return self.single.to_json(obj)

    def PATCH(self, cluster_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        return self.PUT(task_deployment_id, obj_id)

    @content
    def DELETE(self, cluster_id, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        d_e = self.get_object_or_404(self.single, obj_id)
        self.single.delete(d_e)
        raise self.http(204)


class TasksHistoryCollectionHandler(base.CollectionHandler):

    collection = objects.TaskHistoryCollection
    validator = task_history.TaskHistoryValidator

    @content
    def GET(self, task_deployment_id):
        """:returns: Collection of JSONized TasksHistory objects.

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        self.get_object_or_404(objects.Task, task_deployment_id)
        return self.collection.to_json(
            self.collection.get_by_task_deployment_id(task_deployment_id)
        )
