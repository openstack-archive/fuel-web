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

from nailgun.api.v1.handlers.base import TransactionExecutorHandler

from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.validators import deployment_sequence as validators

from nailgun import objects


class SequenceHandler(SingleHandler):
    """Handler for deployment graph related to model."""

    validator = validators.SequenceValidator
    single = objects.DeploymentSequence

    @handle_errors
    @serialize
    def PUT(self, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(self.single, obj_id)

        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )
        self.single.update(obj, data)
        return self.single.to_dict(obj)

    def PATCH(self, obj_id):
        """Update deployment sequence.

        :param obj_id: the deployment sequence id
        :returns:  updated object
        :http: * 200 (OK)
               * 400 (invalid data specified)
               * 404 (object not found in db)

        """
        return self.PUT(obj_id)


class SequenceCollectionHandler(CollectionHandler):
    """Handler for deployment graphs related to the models collection."""

    validator = validators.SequenceValidator
    collection = objects.DeploymentSequenceCollection

    @handle_errors
    @serialize
    def GET(self):
        """:returns: Collection of JSONized Sequence objects by release.

        :http: * 200 (OK)
        :http: * 404 (Release or Cluster is not found)
        """

        release = self._get_release()
        if release:
            return self.collection.get_for_release(release)
        return self.collection.all()

    def _get_release(self):
        params = web.input(release=None, cluster=None)
        if params.cluster:
            return self.get_object_or_404(
                objects.Cluster, id=params.cluster
            ).release
        if params.release:
            return self.get_object_or_404(
                objects.Release, id=params.release
            )


class SequenceExecutorHandler(TransactionExecutorHandler):
    """Handler to execute deployment sequence."""

    validator = validators.SequenceExecutorValidator

    @handle_errors
    def POST(self, obj_id):
        """Execute sequence as single transaction.

        :returns: JSONized Task object

        :http: * 200 (task successfully executed)
               * 202 (task scheduled for execution)
               * 400 (data validation failed)
               * 404 (cluster or sequence not found in db)
               * 409 (graph execution is in progress)
        """
        data = self.checked_data()
        seq = self.get_object_or_404(objects.DeploymentSequence, id=obj_id)
        cluster = self.get_object_or_404(objects.Cluster, data.pop('cluster'))
        if cluster.release_id != seq.release_id:
            raise self.http(
                404,
                "Sequence '{0}' is not found for cluster {1}"
                .format(seq.name, cluster.name)
            )
        data['graphs'] = seq.graphs
        return self.start_transaction(cluster, data)
