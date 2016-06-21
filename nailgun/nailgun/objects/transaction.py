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

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.transaction import TransactionSerializer


class Transaction(NailgunObject):

    model = models.Task
    serializer = TransactionSerializer

    @classmethod
    def get_by_uuid(cls, uuid, fail_if_not_found=False, lock_for_update=False):
        # maybe consider using uuid as pk?
        q = db().query(cls.model).filter_by(uuid=uuid)
        if lock_for_update:
            q = q.order_by('id')
            q = q.with_lockmode('update')
        res = q.first()

        if not res and fail_if_not_found:
            raise errors.ObjectNotFound(
                "Task with UUID={0} is not found in DB".format(uuid)
            )
        return res

    @classmethod
    def attach_deployment_info(cls, instance, deployment_info):
        instance.deployment_info = deployment_info

    @classmethod
    def get_deployment_info(cls, instance):
        if instance is not None:
            return instance.deployment_info

    @classmethod
    def attach_network_settings(cls, instance, settings):
        instance.network_settings = settings

    @classmethod
    def get_network_settings(cls, instance):
        if instance is not None:
            return instance.network_settings

    @classmethod
    def attach_cluster_settings(cls, instance, settings):
        instance.cluster_settings = settings

    @classmethod
    def get_cluster_settings(cls, instance):
        if instance is not None:
            return instance.cluster_settings

    @classmethod
    def attach_tasks_snapshot(cls, instance, tasks_snapshot):
        instance.tasks_snapshot = tasks_snapshot

    @classmethod
    def get_tasks_snapshot(cls, instance):
        if instance is not None:
            return instance.tasks_snapshot


class TransactionCollection(NailgunCollection):

    single = Transaction

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        return cls.filter_by(None, cluster_id=cluster_id)

    @classmethod
    def get_transactions(cls, cluster_id, tasks_names=None, statuses=None):
        query = cls.all()
        if cluster_id:
            query = cls.filter_by(query, cluster_id=cluster_id)
        if tasks_names:
            query = cls.filter_by_list(query, 'name', tasks_names)
        if statuses:
            query = cls.filter_by_list(query, 'status', statuses)
        return query

    @classmethod
    def get_last_succeed_run(cls, cluster):
        # TODO(bgaifullin) remove hardcoded name of task
        return cls.filter_by(
            None, cluster_id=cluster.id, name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.ready
        ).order_by('-id').limit(1).first()

    @classmethod
    def get_successful_transactions_per_task(cls, cluster_id,
                                             task_names=None,
                                             nodes_uids=None):
        """Get last successful transaction for every task name.

        :param cluster_id: db id of cluster object
        :param task_names: list with task names
        :param nodes_uids: db Node uids, which state you need
        :returns: [(Transaction, node_id, task_name), ...]
        """
        history = models.DeploymentHistory
        model = cls.single.model

        transactions = db().query(
            model,
            history.node_id,
            history.deployment_graph_task_name,
        ).join(history).filter(
            model.cluster_id == cluster_id,
            model.name == consts.TASK_NAMES.deployment,
            history.status == consts.HISTORY_TASK_STATUSES.ready,
        )

        if nodes_uids is not None:
            transactions = transactions.filter(
                history.node_id.in_(nodes_uids),
            )

        if task_names is not None:
            transactions = transactions.filter(
                history.deployment_graph_task_name.in_(task_names),
            )

        transactions = transactions.order_by(
            history.deployment_graph_task_name,
            history.node_id,
            history.task_id.desc(),
        ).distinct(
            history.deployment_graph_task_name, history.node_id
        )
        return transactions
