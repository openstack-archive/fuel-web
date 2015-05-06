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

from fuel_upgrade.clients import KeystoneClient
from fuel_upgrade.utils import http_retry


class NailgunClient(object):
    """NailgunClient is a simple wrapper around Nailgun API.

    :param str host: nailgun's host address
    :param (str|int) port: nailgun's port number
    :param dict keystone_credentials: keystone credentials where
                                     `username` is user name
                                     `password` is user password
                                     `auth_url` authentification url
                                     `tenant_name` tenant name
    """

    api_url = 'http://{host}:{port}/api/v1'

    def __init__(self, host=None, port=None, keystone_credentials={}):
        #: an url to nailgun's restapi service
        self.api_url = self.api_url.format(host=host, port=port)
        #: keystone credentials for authentification
        self.keystone_client = KeystoneClient(**keystone_credentials)

    @http_retry(status_codes=[500, 502])
    def get_releases(self):
        """Returns a list with all releases.
        """
        r = self.request.get(
            '{api_url}/releases/'.format(api_url=self.api_url))

        if r.status_code not in (200, ):
            r.raise_for_status()
        return r.json()

    @http_retry(status_codes=[500, 502])
    def create_release(self, release):
        """Add a new release to nailgun database.

        :param release: a given release information, as dict
        """
        r = self.request.post(
            '{api_url}/releases/'.format(api_url=self.api_url),
            data=json.dumps(release))

        if r.status_code not in (201, ):
            r.raise_for_status()

        return r.json()

    @http_retry(status_codes=[500, 502])
    def remove_release(self, release_id):
        """Remove release from Nailgun with a given ID.

        :param release_id: a release id to be removed, as int
        """
        r = self.request.delete(
            '{api_url}/releases/{id}/'.format(
                api_url=self.api_url,
                id=release_id))

        if r.status_code not in (200, 204, ):
            r.raise_for_status()

        # generally, the delete request should returns 204 No Content
        # so we don't want to parse a response as json
        return r.text

    @http_retry(status_codes=[500, 502])
    def create_notification(self, notification):
        """Add a new notification to nailgun database.

        :param notification: a given notification information, as dict
        """
        r = self.request.post(
            '{api_url}/notifications/'.format(api_url=self.api_url),
            data=json.dumps(notification))

        if r.status_code not in (201, ):
            r.raise_for_status()
        return r.json()

    @http_retry(status_codes=[500, 502])
    def remove_notification(self, notification_id):
        """Remove notification from Nailgun with a given ID.

        :param notification_id: a notification id to be removed, as int
        """
        r = self.request.delete(
            '{api_url}/notifications/{id}/'.format(
                api_url=self.api_url,
                id=notification_id))

        if r.status_code not in (200, 204):
            r.raise_for_status()

        # generally, the delete request should returns 204 No Content
        # so we don't want to parse a response as json
        return r.text

    @http_retry(status_codes=[500, 502])
    def get_tasks(self):
        """Retrieve list of tasks from nailgun

        :returns: list of tasks
        """
        r = self.request.get('{api_url}/tasks'.format(api_url=self.api_url))

        if r.status_code not in (200, ):
            r.raise_for_status()

        return r.json()

    @property
    def request(self):
        """Creates authentification session if required

        :returns: :class:`requests.Session` object
        """
        return self.keystone_client.request

    @http_retry(status_codes=[500, 502])
    def put_deployment_tasks(self, release, tasks):
        """Update deployment tasks for certain release

        :param release: release as dict
        :param tasks: deployment tasks as lists of dicts
        """
        r = self.request.put(
            '{api_url}/releases/{release_id}/deployment_tasks'.format(
                api_url=self.api_url, release_id=release['id']),
            data=json.dumps(tasks))

        if r.status_code not in (200, ):
            r.raise_for_status()
        return r.json()
