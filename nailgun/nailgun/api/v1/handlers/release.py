#    Copyright 2013 Mirantis, Inc.
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

"""
Handlers dealing with releases
"""

from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import OrchestratorDeploymentTasksHandler
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.handlers.base import validate
from nailgun.api.v1.handlers.deployment_graph import \
    RelatedDeploymentGraphCollectionHandler
from nailgun.api.v1.handlers.deployment_graph import \
    RelatedDeploymentGraphHandler
from nailgun.api.v1.validators.release import \
    ReleaseAttributesMetadataValidator
from nailgun.api.v1.validators.release import ReleaseNetworksValidator
from nailgun.api.v1.validators.release import ReleaseValidator
from nailgun.objects import Release
from nailgun.objects import ReleaseCollection


class ReleaseHandler(SingleHandler):
    """Release single handler"""

    single = Release
    validator = ReleaseValidator


class ReleaseAttributesMetadataHandler(SingleHandler):
    """Release attributes metadata handler"""

    single = Release
    validator = ReleaseAttributesMetadataValidator

    @handle_errors
    @validate
    @serialize
    def GET(self, obj_id):
        """:returns: JSONized Release attributes metadata.

        :http: * 200 (OK)
               * 404 (release not found in db)
        """
        release = self.get_object_or_404(self.single, obj_id)
        return release['attributes_metadata']

    @handle_errors
    @validate
    @serialize
    def PUT(self, obj_id):
        """:returns: JSONized Release attributes metadata.

        :http: * 200 (OK)
               * 400 (wrong data specified)
               * 404 (release not found in db)
        """
        release = self.get_object_or_404(self.single, obj_id)
        data = self.checked_data()
        self.single.update(release, {'attributes_metadata': data})
        return release['attributes_metadata']


class ReleaseCollectionHandler(CollectionHandler):
    """Release collection handler"""

    validator = ReleaseValidator
    collection = ReleaseCollection

    @handle_errors
    @validate
    @serialize
    def GET(self):
        """:returns: Sorted releases' collection in JSON format

        :http: * 200 (OK)
        """
        q = sorted(self.collection.all(), reverse=True)
        return self.collection.to_list(q)


class ReleaseNetworksHandler(SingleHandler):
    """Release Handler for network metadata"""

    single = Release
    validator = ReleaseNetworksValidator

    @handle_errors
    @validate
    @serialize
    def GET(self, obj_id):
        """Read release networks metadata

        :returns: Release networks metadata
        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 404 (release object not found)
        """
        obj = self.get_object_or_404(self.single, obj_id)
        return obj['networks_metadata']

    @handle_errors
    @validate
    @serialize
    def PUT(self, obj_id):
        """Updates release networks metadata

        :returns: Release networks metadata
        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 404 (release object not found)
        """
        obj = self.get_object_or_404(self.single, obj_id)
        data = self.checked_data()
        self.single.update(obj, {'networks_metadata': data})
        return obj['networks_metadata']

    def POST(self, obj_id):
        """Creation of metadata disallowed

        :http: * 405 (method not supported)
        """
        raise self.http(405, 'Create not supported for this entity')

    def DELETE(self, obj_id):
        """Deletion of metadata disallowed

        :http: * 405 (method not supported)
        """
        raise self.http(405, 'Delete not supported for this entity')


class ReleaseDeploymentTasksHandler(OrchestratorDeploymentTasksHandler):
    """Release Handler for deployment tasks configuration (legacy)."""

    single = Release


class ReleaseDeploymentGraphHandler(RelatedDeploymentGraphHandler):
    """Release Handler for deployment graph configuration."""

    related = Release


class ReleaseDeploymentGraphCollectionHandler(
        RelatedDeploymentGraphCollectionHandler):
    """Release Handler for deployment graphs configuration."""

    related = Release
