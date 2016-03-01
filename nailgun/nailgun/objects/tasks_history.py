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
from nailgun.db.sqlalchemy import models

from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.tasks_history \
    import TasksHistorySerializer

from nailgun.logger import logger


class TasksHistory(NailgunObject):

    model = models.TasksHistory
    serializer = TasksHistorySerializer

    @classmethod
    def update(cls, deployment_task_id, node_id, task_name, status, summary):
        task_history = db().query(cls.model)\
            .filter_by(deployment_task_id=deployment_task_id)\
            .filter_by(task_name=task_name)\
            .filter_by(node_id=node_id)\
            .first()

        task_history.status = status
        task_history.summary = summary


class TasksHistoryCollection(NailgunCollection):

    single = TasksHistory

    @classmethod
    def create(cls, deployment_task, tasks_graph):
        for node_id in tasks_graph:
            if not node_id or node_id == 'master':
                continue
            for task in tasks_graph[node_id]:
                if not task.get('id'):
                    logger.debug("Task name missing. Ignoring %s", task)
                    continue
                task_history = cls.single.model(
                    deployment_task_id=deployment_task.id,
                    node_id=node_id,
                    task_name=task['id'])
                db().add(task_history)

        db().flush()

    @classmethod
    def get_by_deployment_task_id(cls, deployment_task_id):
        if deployment_task_id == '':
            return cls.filter_by(None, deployment_task_id=None)
        return cls.filter_by(None, deployment_task_id=deployment_task_id)
