# -*- coding: utf-8 -*-

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

from fuel_upgrade import errors
from fuel_upgrade import utils


class PyNailgun(object):
    """PyNailgun is a simple wrapper around Nailgun API.
    """

    api_url = 'http://{host}:{port}/api/v1'

    def __init__(self, host, port):
        """Initialize PyNailgun object with a given config.
        """
        #: an url to nailgun's restapi service
        self.api_url = self.api_url.format(host=host, port=port)

    def create_release(self, release):
        """Add a new release to nailgun database.

        :param release: a given release information, as dict
        """
        resource_url = '{api_url}/releases/'.format(api_url=self.api_url)
        response, status_code = utils.post_request(resource_url, release)

        # if not created
        if status_code != 201:
            raise errors.FailedApiCall(response)

        return response

    def remove_release(self, release_id):
        """Remove release from Nailgun with a given ID.

        :param release_id: a release id to be removed, as int
        """
        resource_url = '{api_url}/releases/{id}/'.format(
            api_url=self.api_url,
            id=release_id
        )
        response, status_code = utils.delete_request(resource_url)

        if status_code not in (200, 204):
            raise errors.FailedApiCall(response)

        return response

    def create_notification(self, notification):
        """Add a new notification to nailgun database.

        :param notification: a given notification information, as dict
        """
        resource_url = '{api_url}/notifications/'.format(api_url=self.api_url)
        response, status_code = utils.post_request(resource_url, notification)

        # if not created
        if status_code != 201:
            raise errors.FailedApiCall(response)

        return response

    def remove_notification(self, notification_id):
        """Remove notification from Nailgun with a given ID.

        :param notification_id: a notification id to be removed, as int
        """
        resource_url = '{api_url}/notifications/{id}/'.format(
            api_url=self.api_url,
            id=notification_id
        )
        response, status_code = utils.delete_request(resource_url)

        if status_code not in (200, 204):
            raise errors.FailedApiCall(response)

        return response
