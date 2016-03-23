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

        getattr(cls, 'to_{0}'.format(status))(deployment_history)

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
        for node_id in tasks_graph:
            history_node_id = node_id if node_id else 'null'
            for graph_task in tasks_graph[node_id]:
                if not graph_task.get('id'):
                    logger.debug("Task name missing. Ignoring %s", graph_task)
                    continue
                deployment_history = cls.single.model(
                    task_id=task.id,
                    node_id=history_node_id,
                    deployment_graph_task_name=graph_task['id'])
                db().add(deployment_history)

        db().flush()

    @classmethod
    def get_by_transaction_id(cls, transaction_id):
        return cls.filter_by(None, task_id=transaction_id)

    @classmethod
    def get_history(cls, transaction_id, node_ids=None, statuses=None):
        history_query = cls.get_by_transaction_id(transaction_id)

        if node_ids and statuses:
            h_q = cls.filter_by_list(history_query, 'node_id', node_ids)
            return cls.filter_by_list(h_q, 'status', statuses)
        elif node_ids and not statuses:
            return cls.filter_by_list(history_query, 'node_id', node_ids)
        elif statuses and not node_ids:
            return cls.filter_by_list(history_query, 'status', statuses)

        return history_query
