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

from nailgun.api.v1.handlers.base import content_json
from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import SingleHandler

from nailgun.api.v1.validators.release import ReleaseValidator

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
        """:returns: Releases' collection in JSON format
        :http: * 200 (OK)
        """
        q = self.collection.eager(None, self.eager)
        q_sorted = ReleaseCollection.order_by(q, '-operating_system')
        return self.collection.to_json(q_sorted)
