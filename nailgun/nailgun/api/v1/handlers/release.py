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

import os
import uuid

import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.handlers.base import DeploymentTasksHandler
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.validators.release import ReleaseNetworksValidator
from nailgun.api.v1.validators.release import ReleaseValidator
from nailgun.task.manager import PrepareReleaseTaskManager

from nailgun.db import db

from nailgun.objects import Release
from nailgun.objects import ReleaseCollection
from nailgun.objects import Task

from nailgun.consts import RELEASE_STATES
from nailgun.settings import settings
from nailgun import utils


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

    @content
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

    @content
    def GET(self, obj_id):
        """Read release networks metadata

        :returns: Release networks metadata
        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 404 (release object not found)
        """
        obj = self.get_object_or_404(self.single, obj_id)
        return obj['networks_metadata']

    @content
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


class ReleaseDeploymentTasksHandler(DeploymentTasksHandler):
    """Release Handler for deployment graph configuration."""

    single = Release


class ReleaseUploadISO(BaseHandler):
    """Release handler for uploading ISO."""

    single = Release
    task_manager = PrepareReleaseTaskManager

    def POST(self, obj_id):
        release = self.get_object_or_404(self.single, obj_id)

        if release.state == RELEASE_STATES.available:
            raise self.http(405, (
                "The request couldn't be performed for 'available' "
                "release."))

        if not self.single.set_state(release, RELEASE_STATES.processing):
            raise self.http(409, (
                "Unable to perform the request. Perhaps, it's already "
                "in progress. If not, please try again."))
        # let's commit .state changes, so other workers see these changes
        # and show user error if he wants to upload iso again.
        db.commit()

        # TODO(ikalntisky): consider to use tempfile module
        save_as = os.path.join(
            settings.IMAGE_UPLOAD_PATH, '{0}.iso'.format(uuid.uuid4()))

        with open(save_as, mode='wb') as output_stream:
            # there's no way to get stream by using pure web.py api, so
            # we forced to get it through web.py internals
            input_stream = web.ctx.env['wsgi.input']
            sha1 = utils.upload_image(input_stream, output_stream)  # noqa

        # if checksum validation has been failed there's no sense to keep
        # going. so, let's return unavailable state for release and remove
        # uploaded file.
        if False:   # TODO(ikalnitsky): check SHA1 sum
            # TODO(ikalnitsky): remove temp file
            self.single.set_state(release, RELEASE_STATES.unavailable)
            db.commit()
            raise self.http(400)    # TODO(ikalnitsky): add message

        task = self.task_manager().execute(release, save_as)
        raise self.http(202, Task.to_json(task))

    def PUT(self, obj_id):
        self.POST(obj_id)
