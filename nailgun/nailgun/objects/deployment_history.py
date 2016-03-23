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


from datetime import datetime

from nailgun.consts import HISTORY_TASK_STATUSES
from nailgun.db import db
from nailgun.db.sqlalchemy import models


from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.deployment_history \
    import DeploymentHistorySerializer

from nailgun.logger import logger


class DeploymentHistory(NailgunObject):

    model = models.DeploymentHistory
    serializer = DeploymentHistorySerializer

    @classmethod
    def update_if_exist(cls, task_id, node_id, deployment_graph_task_name,
                        status, custom):
        deployment_history = cls.find_history(task_id, node_id,
                                              deployment_graph_task_name)

        if not deployment_history:
            return

        status_action = {
            HISTORY_TASK_STATUSES.ready: cls.to_ready,
            HISTORY_TASK_STATUSES.error: cls.to_error,
            HISTORY_TASK_STATUSES.skipped: cls.to_skipped,
            HISTORY_TASK_STATUSES.running: cls.to_running,
            HISTORY_TASK_STATUSES.pending: cls.to_pending}

        status_action.get(status)(deployment_history)

    @classmethod
    def find_history(cls, task_id, node_id, deployment_graph_task_name):
        return db().query(cls.model)\
            .filter_by(task_id=task_id,
                       node_id=node_id,
                       deployment_graph_task_name=deployment_graph_task_name)\
            .first()

    @classmethod
    def to_ready(cls, deployment_history):
        deployment_history.status = HISTORY_TASK_STATUSES.ready
        cls._set_time_end(deployment_history)

    @classmethod
    def to_error(cls, deployment_history):
        deployment_history.status = HISTORY_TASK_STATUSES.error
        cls._set_time_end(deployment_history)

    @classmethod
    def to_skipped(cls, deployment_history):
        deployment_history.status = HISTORY_TASK_STATUSES.skipped
        cls._set_time_start(deployment_history)
        cls._set_time_end(deployment_history)

    @classmethod
    def to_running(cls, deployment_history):
        deployment_history.status = HISTORY_TASK_STATUSES.running
        cls._set_time_start(deployment_history)

    @classmethod
    def to_pending(cls, deployment_history):
        pass

    @classmethod
    def _set_time_end(cls, deployment_history):
        if not deployment_history.time_end:
            deployment_history.time_end = datetime.utcnow()

    @classmethod
    def _set_time_start(cls, deployment_history):
        if not deployment_history.time_start:
            deployment_history.time_start = datetime.utcnow()


class DeploymentHistoryCollection(NailgunCollection):

    single = DeploymentHistory

    @classmethod
    def create(cls, task, tasks_graph):
        d_histories = []
        for node_id in tasks_graph:
            for graph_task in tasks_graph[node_id]:
                if not graph_task.get('id'):
                    logger.warn("Task name missing. Ignoring %s", graph_task)
                    continue
                d_histories.append(cls.single.model(
                    task_id=task.id,
                    node_id=node_id,
                    deployment_graph_task_name=graph_task['id']))

        if d_histories:
            db().bulk_save_objects(d_histories)

    @classmethod
    def get_history(cls, transaction_id, node_ids=None, statuses=None):
        history_query = cls.filter_by(None, task_id=transaction_id)
        model = cls.single.model

        if node_ids:
            history_query = history_query.filter(model.node_id.in_(node_ids))
        if statuses:
            history_query = history_query.filter(model.status.in_(statuses))

        return history_query
