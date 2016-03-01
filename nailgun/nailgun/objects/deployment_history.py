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

from nailgun.consts import TASK_STATUSES
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
    def update(cls, task_id, node_id, deployment_graph_task_name,
               status, custom):
        deployment_history = db().query(cls.model)\
            .filter_by(task_id=task_id)\
            .filter_by(deployment_graph_task_name=deployment_graph_task_name)\
            .filter_by(node_id=node_id)\
            .first()

        if not deployment_history:
            return

        deployment_history.status = status

        if not deployment_history.time_start and \
                deployment_history.status != TASK_STATUSES.pending:
            deployment_history.time_start = datetime.utcnow()
        if deployment_history.status in [TASK_STATUSES.ready, TASK_STATUSES.error] \
                and not deployment_history.time_end:
            deployment_history.time_end = datetime.utcnow()


class DeploymentHistoryCollection(NailgunCollection):

    single = DeploymentHistory

    @classmethod
    def create(cls, task, tasks_graph):
        for node_id in tasks_graph:
            if not node_id:
                continue
            for graph_task in tasks_graph[node_id]:
                if not graph_task.get('id'):
                    logger.debug("Task name missing. Ignoring %s", graph_task)
                    continue
                if graph_task.get('type') == 'skipped':
                    continue
                deployment_history = cls.single.model(
                    task_id=task.id,
                    node_id=node_id,
                    deployment_graph_task_name=graph_task['id'])
                db().add(deployment_history)

        db().flush()

    @classmethod
    def get_by_transaction_id(cls, transaction_id):
        if transaction_id == '':
            return cls.filter_by(None, task_id=None)
        return cls.filter_by(None, task_id=transaction_id)
