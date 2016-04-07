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
import copy
from datetime import datetime

from nailgun.consts import HISTORY_TASK_STATUSES
from nailgun.db import db
from nailgun.db.sqlalchemy import models


from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.deployment_history \
    import DeploymentHistorySerializer
from nailgun.objects import Transaction

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
            logger.warn("Failed to find task in history for transaction id %s"
                        ", node_id %s and deployment_graph_task_name %s",
                        task_id, node_id, deployment_graph_task_name)
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
        if deployment_history.status == HISTORY_TASK_STATUSES.running:
            deployment_history.status = HISTORY_TASK_STATUSES.ready
            cls._set_time_end(deployment_history)
        else:
            cls._logging_wrong_status_change(deployment_history.status,
                                             HISTORY_TASK_STATUSES.ready)

    @classmethod
    def to_error(cls, deployment_history):
        if deployment_history.status == HISTORY_TASK_STATUSES.running:
            deployment_history.status = HISTORY_TASK_STATUSES.error
            cls._set_time_end(deployment_history)
        else:
            cls._logging_wrong_status_change(deployment_history.status,
                                             HISTORY_TASK_STATUSES.error)

    @classmethod
    def to_skipped(cls, deployment_history):
        if deployment_history.status == HISTORY_TASK_STATUSES.pending:
            deployment_history.status = HISTORY_TASK_STATUSES.skipped
            cls._set_time_start(deployment_history)
            cls._set_time_end(deployment_history)
        else:
            cls._logging_wrong_status_change(deployment_history.status,
                                             HISTORY_TASK_STATUSES.skipped)

    @classmethod
    def to_running(cls, deployment_history):
        if deployment_history.status == HISTORY_TASK_STATUSES.pending:
            deployment_history.status = HISTORY_TASK_STATUSES.running
            cls._set_time_start(deployment_history)
        else:
            cls._logging_wrong_status_change(deployment_history.status,
                                             HISTORY_TASK_STATUSES.running)

    @classmethod
    def to_pending(cls, deployment_history):
        cls._logging_wrong_status_change(deployment_history.status,
                                         HISTORY_TASK_STATUSES.pending)

    @classmethod
    def _set_time_end(cls, deployment_history):
        if not deployment_history.time_end:
            deployment_history.time_end = datetime.utcnow()

    @classmethod
    def _set_time_start(cls, deployment_history):
        if not deployment_history.time_start:
            deployment_history.time_start = datetime.utcnow()

    @classmethod
    def _logging_wrong_status_change(cls, from_status, to_status):
        logger.warn("Error status transition from %s to %s",
                    from_status, to_status)


class DeploymentHistoryCollection(NailgunCollection):

    single = DeploymentHistory

    @classmethod
    def create(cls, task, tasks_graph):
        entries = []
        for node_id in tasks_graph:
            for graph_task in tasks_graph[node_id]:
                if not graph_task.get('id'):
                    logger.warn("Task name missing. Ignoring %s", graph_task)
                    continue
                entries.append(cls.single.model(
                    task_id=task.id,
                    node_id=node_id,
                    deployment_graph_task_name=graph_task['id']))

        db().bulk_save_objects(entries)

    @classmethod
    def get_history(cls, transaction, nodes_ids=None, statuses=None,
                    tasks_names=None):
        """Get deployment tasks history.

        :param transaction: transaction SQLAlchemy object
        :type transaction: models.Transaction
        :param nodes_ids: filter by node IDs
        :type nodes_ids: list[int]|None
        :param statuses: filter by statuses
        :type statuses: list[basestring]|None
        :param tasks_names: filter by deployment graph task names
        :type tasks_names: list[basestring]|None
        :returns: tasks history
        :rtype: list[dict]
        """
        query = cls.filter_by(None, task_id=transaction.id)
        if nodes_ids:
            query = query.filter(cls.single.model.node_id.in_(nodes_ids))
        if statuses:
            query = query.filter(cls.single.model.status.in_(statuses))
        if tasks_names:
            query = query.filter(
                cls.single.model.deployment_graph_task_name.in_(tasks_names))

        history = copy.deepcopy(cls.to_list(query))

        for record in history:
            # rename task id to conventional field
            record['task_name'] = record['deployment_graph_task_name']
            record.pop('deployment_graph_task_name', None)

        tasks_snapshot = Transaction.get_tasks_snapshot(transaction)

        if tasks_snapshot:
            task_by_name = {}

            for task in tasks_snapshot:
                # remove ambiguous id field
                task.pop('id', None)
                task_by_name[task['task_name']] = task

            for history_record in history:
                task_name = history_record.get('task_name')
                try:
                    task_parameters = task_by_name[task_name]
                    history_record.update(task_parameters)
                except KeyError:
                    logger.warning(
                        'Definition of "{0}" task is not found'.format(
                            task_name))
        else:
            logger.warning('No tasks snapshot is defined in given '
                           'transaction, probably it is a legacy '
                           '(Fuel<10.0) or malformed.')
        return history
