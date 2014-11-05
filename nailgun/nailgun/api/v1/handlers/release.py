# -*- coding: utf-8 -*-

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
from nailgun.api.v1.handlers.base import content_json
from nailgun.api.v1.handlers.base import SingleHandler

from nailgun.api.v1.validators.release import ReleaseValidator
from nailgun.api.v2.validators.release import ReleaseNetworksValidator

from nailgun.objects import Release
from nailgun.objects import ReleaseCollection


class ReleaseHandler(SingleHandler):
    """Release single handler
    """

    single = Release
    validator = ReleaseValidator


class ReleaseCollectionHandler(CollectionHandler):
    """Release collection handler
    """

    validator = ReleaseValidator
    collection = ReleaseCollection

    @content_json
    def GET(self):
        """:returns: Sorted releases' collection in JSON format
        :http: * 200 (OK)
        """
        q = sorted(self.collection.all(), reverse=True)
        return self.collection.to_json(q)


class ReleaseNetworksHandler(SingleHandler):
    """Release Handler for network metadata
    """

    single = Release
    validator = ReleaseNetworksValidator

    @content_json
    def GET(self, obj_id):
        """
        :returns: Release networks metadata
        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 404 (release object not found)
        """
        obj = self.get_object_or_404(self.single, obj_id)
        self.validator.validate_schema(obj['networks_metadata'])
        return obj['networks_metadata']

    @content_json
    def PUT(self, obj_id):
        """
        :returns: Release networks metadata
        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 404 (release object not found)
        """
        obj = self.get_object_or_404(self.single, obj_id)

        data = self.checked_data(
            self.validator.validate,
            instance=obj
        )
        self.single.update(obj, data['networks_metadata'])

    def POST(self, obj_id):
        """
        :http: $ 405 (method not supported)
        """
        raise self.http(405, 'Create not supported for this entity')

    def DELETE(self):
        """
        :http: $ 405 (method not supported)
        """
        raise self.http(405, 'Delete not supported for this entity')
