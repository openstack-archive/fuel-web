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

from nailgun.db import db
from nailgun.db.sqlalchemy.models import tasks_history \
    as tasks_history_db_model
from nailgun.objects import base


class TasksHistory(base.NailgunObject):

    model = tasks_history_db_model.TasksHistory
    serializer = tasks_history_db_model.TasksHistorySerializer


class TasksHistoryCollection(base.NailgunCollection):

    single = TasksHistory

    @classmethod
    def create(cls, deployment_task_id, tasks_graph):
        for node_id in tasks_graph:
            for task in tasks_graph[node_id]:
                task_history = TasksHistory(
                    deployment_task_id=deployment_task_id,
                    node_id=node_id,
                    task_id=task['id'])
                db.add(task_history)

    @classmethod
    def get_by_task_deployment_id(cls, task_deployment_id):
        if task_deployment_id == '':
            return cls.filter_by(None, task_deployment_id=None)
        return cls.filter_by(None, task_deployment_id=task_deployment_id)
