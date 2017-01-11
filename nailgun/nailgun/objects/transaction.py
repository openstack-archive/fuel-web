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

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.node_deployment_info import NodeDeploymentInfo
from nailgun.objects.node_deployment_info import NodeDeploymentInfoCollection
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
        for uid, dinfo in deployment_info['nodes'].items():
            NodeDeploymentInfo.create({'task_id': instance.id,
                                       'node_uid': uid,
                                       'deployment_info': dinfo})
        if 'common' in deployment_info:
            instance.deployment_info = deployment_info['common']

    @classmethod
    def get_deployment_info(cls, instance, node_uids=None):
        if instance is None:
            return {}

        node_di_list = NodeDeploymentInfoCollection.filter_by(
            None, task_id=instance.id)
        if node_uids:
            node_di_list = NodeDeploymentInfoCollection.filter_by_list(
                node_di_list, "node_uid", node_uids)

        nodes_info = {node_di.node_uid: node_di.deployment_info
                      for node_di in node_di_list}
        if nodes_info or instance.deployment_info:
            return {'common': instance.deployment_info or {},
                    'nodes': nodes_info}
        return {}

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

    @classmethod
    def on_start(cls, instance):
        cls.update(instance, {
            'time_start': datetime.utcnow(),
            'status': consts.TASK_STATUSES.running
        })

    @classmethod
    def on_finish(cls, instance, status, message=None):
        data = {
            'progress': 100,
            'status': status,
            'time_end': datetime.utcnow(),
        }
        if message is not None:
            data['message'] = message

        # set time start the same time of there is no time start
        cls.update(instance, data)


class TransactionCollection(NailgunCollection):

    single = Transaction

    @classmethod
    def get_transactions(cls, cluster_id=None,
                         transaction_types=None,
                         statuses=None):
        """Get list of transactions by given filters.

        :param cluster_id: db id of cluster object
        :param transaction_types: list with transaction types
        :param statuses: list of statuses
        :returns: list of Task objects
        """
        query = cls.all()
        if cluster_id:
            query = cls.filter_by(query, cluster_id=cluster_id)
        if transaction_types:
            query = cls.filter_by_list(query, 'name', transaction_types)
        if statuses:
            query = cls.filter_by_list(query, 'status', statuses)
        return query

    @classmethod
    def get_last_succeed_run(cls, cluster):
        # TODO(bgaifullin) remove hardcoded name of task
        return cls.filter_by(
            None, cluster_id=cluster.id, name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.ready, dry_run=False,
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
            model.dry_run.is_(False),
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
