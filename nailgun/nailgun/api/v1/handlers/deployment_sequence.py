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

from nailgun.api.v1.handlers.base import TransactionExecutorHandler

from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.validators import deployment_sequence as validators

from nailgun import objects


class SequenceHandler(SingleHandler):
    """Handler for deployment graph related to model."""

    validator = validators.SequenceValidator
    single = objects.DeploymentSequence

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


class SequenceExecutorHandler(TransactionExecutorHandler):
    """Handler to execute deployment sequence."""

    validator = validators.SequenceExecutorValidator
