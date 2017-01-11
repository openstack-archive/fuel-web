#    Copyright 2015 Mirantis, Inc.
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

from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import validate
from nailgun.objects import Release
from nailgun.objects.serializers.release import ComponentSerializer


class ComponentCollectionHandler(CollectionHandler):
    """Component collection handler"""

    @handle_errors
    @validate
    @serialize
    def GET(self, release_id):
        """:returns: JSONized component data for release and related plugins.

        :http: * 200 (OK)
               * 404 (release not found in db)
        """
        release = self.get_object_or_404(Release, release_id)
        components = Release.get_all_components(release)

        return [ComponentSerializer.serialize(c) for c in components]

    def POST(self, release_id):
        """Creating of components is disallowed

        :http: * 405 (method not supported)
        """
        raise self.http(405, 'Create not supported for this entity')
