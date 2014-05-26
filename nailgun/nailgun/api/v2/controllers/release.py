#    Copyright 2014 Mirantis, Inc.
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

import pecan

from nailgun.api.v1.validators.release import ReleaseValidator
from nailgun.api.v2.controllers.base import BaseController
from nailgun.api.v2.controllers.base import DeploymentTasksController

from nailgun.objects import Release
from nailgun.objects import ReleaseCollection


class ReleaseDeploymentTasksController(DeploymentTasksController):
    """Release Handler for deployment graph configuration.
    """

    single = Release

    # HACK(pkaminski)
    @pecan.expose(template='json:', content_type='application/json')
    def post(self, release_id):
        return super(ReleaseDeploymentTasksController, self).post()


class ReleaseController(BaseController):
    """Release single handler
    """

    deployment_tasks = ReleaseDeploymentTasksController()

    single = Release
    collection = ReleaseCollection
    validator = ReleaseValidator

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """:returns: Collection of JSONized REST objects.
        :http: * 200 (OK)
        """
        q = self.collection.eager(None, self.eager)
        return sorted(
            self.collection.to_list(q),
            key=lambda c: (c['version'], c['operating_system'], c['name']),
            reverse=True
        )
