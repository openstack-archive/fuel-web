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
import web

from nailgun.api.v1.handlers import base
from nailgun.api.v1.handlers.base import content
from nailgun import errors
from nailgun import objects


class BaseDeploymentHistoryCollectionHandler(base.CollectionHandler):

    collection = objects.DeploymentHistoryCollection

    @content
    def GET(self, transaction_id, deployment_task_name=None):
        """:returns: Collection of JSONized DeploymentHistory records.

        :http: * 200 (OK)
               * 404 (transaction not found in db, task not found in snapshot)
        """
        # get transaction data
        transaction = self.get_object_or_404(
            objects.Transaction, transaction_id)

        graph_tasks = objects.Transaction.get_tasks_snapshot(transaction)

        # process input parameters
        node_ids = web.input(nodes=None).nodes
        statuses = web.input(statuses=None).statuses

        if node_ids:
            node_ids = set(node_ids.strip().split(','))
        if statuses:
            statuses = set(statuses.strip().split(','))
        if deployment_task_name:
            task_in_snapshot = next(
                (t for t in graph_tasks if
                 t.get('id') == deployment_task_name),
                None
            )
            if not task_in_snapshot:
                raise self.http(404, 'Definition of "{0}" task is not found'
                                .format(deployment_task_name))
            deployment_task_name = [deployment_task_name]

        # fetch and serialize history
        history = self.collection.to_list(
            self.collection.get_history(
                transaction_id=transaction_id,
                node_ids=node_ids,
                statuses=statuses,
                deployment_task_names=deployment_task_name
            )
        )

        try:
            result = self.collection.unwrap_tasks_definitions(
                history, graph_tasks)
        except errors.TaskNotFoundInHistory as exc:
            raise self.http(404, exc.message)

        return result

    @content
    def POST(self, obj_id):
        """Update of a history is not allowed

        :http: * 405 (Method not allowed)
        """
        raise self.http(405)


class DeploymentHistoryCollectionHandler(
        BaseDeploymentHistoryCollectionHandler):

    def GET(self, transaction_id):
        """:returns: Collection of JSONized DeploymentHistory records.

            :http: * 200 (OK)
                   * 404 (transaction not found in db)
            """
        return super(DeploymentHistoryCollectionHandler, self).GET(
            transaction_id=transaction_id)


class DeploymentHistoryTaskCollectionHandler(
        BaseDeploymentHistoryCollectionHandler):

    def GET(self, transaction_id, deployment_task_name):
        """:returns: Collection of JSONized DeploymentHistory records.

            :http: * 200 (OK)
                   * 404 (transaction not found in db or task not found in
                         deployment graph snapshot)
            """
        return super(DeploymentHistoryTaskCollectionHandler, self).GET(
            transaction_id=transaction_id,
            deployment_task_name=deployment_task_name)
