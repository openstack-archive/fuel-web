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

import json
import requests


class NailgunClient(object):
    """NailgunClient is a simple wrapper around Nailgun API.

    :param host: (str) a nailgun's host address
    :param port: (str|int) a nailgun's port number
    """

    api_url = 'http://{host}:{port}/api/v1'

    def __init__(self, host, port):
        #: an url to nailgun's restapi service
        self.api_url = self.api_url.format(host=host, port=port)

    def get_releases(self):
        """Returns a list with all releases.
        """
        r = requests.get(
            '{api_url}/releases/'.format(
                api_url=self.api_url
            )
        )

        if r.status_code not in (200, ):
            r.raise_for_status()
        return r.json()

    def create_release(self, release):
        """Add a new release to nailgun database.

        :param release: a given release information, as dict
        """
        r = requests.post(
            '{api_url}/releases/'.format(
                api_url=self.api_url
            ),
            data=json.dumps(release)
        )

        if r.status_code not in (201, ):
            r.raise_for_status()
        return r.json()

    def remove_release(self, release_id):
        """Remove release from Nailgun with a given ID.

        :param release_id: a release id to be removed, as int
        """
        r = requests.delete(
            '{api_url}/releases/{id}/'.format(
                api_url=self.api_url,
                id=release_id
            )
        )

        if r.status_code not in (200, 204, ):
            r.raise_for_status()

        # generally, the delete request should returns 204 No Content
        # so we don't want to parse a response as json
        return r.text

    def create_notification(self, notification):
        """Add a new notification to nailgun database.

        :param notification: a given notification information, as dict
        """
        r = requests.post(
            '{api_url}/notifications/'.format(
                api_url=self.api_url
            ),
            data=json.dumps(notification)
        )

        if r.status_code not in (201, ):
            r.raise_for_status()
        return r.json()

    def remove_notification(self, notification_id):
        """Remove notification from Nailgun with a given ID.

        :param notification_id: a notification id to be removed, as int
        """
        r = requests.delete(
            '{api_url}/notifications/{id}/'.format(
                api_url=self.api_url,
                id=notification_id
            )
        )

        if r.status_code not in (200, 204):
            r.raise_for_status()

        # generally, the delete request should returns 204 No Content
        # so we don't want to parse a response as json
        return r.text

    def get_tasks(self):
        """Retrieve list of tasks from nailgun

        :returns: list of tasks
        """
        r = requests.get('{api_url}/tasks'.format(api_url=self.api_url))

        if r.status_code not in (200, ):
            r.raise_for_status()

        return r.json()
