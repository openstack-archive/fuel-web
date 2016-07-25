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

from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.tasks import TaskHandler

from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import validate
from nailgun.api.v1.validators.task import TaskValidator

from nailgun import objects


"""
Handlers dealing with all transactions (tasks)
"""


class TransactionHandler(TaskHandler):
    """Transaction single handler"""

    single = objects.Transaction


class TransactionCollectionHandler(CollectionHandler):
    """Transaction collection handler"""

    collection = objects.TransactionCollection
    validator = TaskValidator

    @handle_errors
    @validate
    @serialize
    def GET(self):
        """May receive cluster_id parameter to filter list of tasks

        :returns: Collection of JSONized Task objects.
        :http: * 200 (OK)
               * 404 (task not found in db)
        """
        cluster_id = web.input(cluster_id=None).cluster_id
        if cluster_id:
            return self.collection.to_json(
                self.collection.get_by_cluster_id(cluster_id)
            )
        else:
            return self.collection.to_json()


class BaseTransactionDataHandler(TransactionHandler):

    get_data = None

    @handle_errors
    @validate
    @serialize
    def GET(self, transaction_id):
        """:returns: Collection of JSONized DeploymentInfo objects.

        :http: * 200 (OK)
               * 404 (cluster not found in db)
        """
        transaction = self.get_object_or_404(objects.Transaction,
                                             transaction_id)
        return self.get_data(transaction)


class TransactionDeploymentInfo(BaseTransactionDataHandler):

    get_data = objects.Transaction.get_deployment_info


class TransactionClusterSettings(BaseTransactionDataHandler):

    get_data = objects.Transaction.get_cluster_settings


class TransactionNetworkSettings(BaseTransactionDataHandler):

    get_data = objects.Transaction.get_network_settings
