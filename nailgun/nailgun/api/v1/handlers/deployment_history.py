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
from nailgun import objects


class DeploymentHistoryCollectionHandler(base.CollectionHandler):

    collection = objects.DeploymentHistoryCollection

    @content
    def GET(self, transaction_id):
        """:returns: Collection of JSONized DeploymentHistory objects.

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        self.get_object_or_404(objects.Transaction, transaction_id)
        node_ids = web.input(nodes=None).nodes
        statuses = web.input(statuses=None).statuses

        if node_ids:
            node_ids = set(node_ids.strip().split(','))
        if statuses:
            statuses = set(statuses.strip().split(','))

        return self.collection.to_json(
            self.collection.get_history(
                transaction_id,
                node_ids,
                statuses)
        )


class DeploymentHistoryTaskHandler(base.CollectionHandler):

    collection = objects.DeploymentHistoryCollection

    @content
    def GET(self, transaction_id, deployment_task_name):
        """:returns: JSONized DeploymentHistory tasks object

        :http: * 200 (OK)
               * 404 (transaction not found in db)
        """
        transaction = self.get_object_or_404(
            objects.Transaction, transaction_id)

        graph_tasks = objects.Transaction.get_graph_snapshot(transaction)

        task = next(
            t for t in graph_tasks
            if t.get('id') == deployment_task_name
        )
        if not task:
            raise self.http(404, 'Definition of "{0}" task not found'
                            .format(deployment_task_name))

        history = self.collection.to_json(
            self.collection.get_history(
                transaction_id=transaction_id,
                deployment_graph_task_names=[deployment_task_name]
            )
        )
        task['history'] = history
        return task
