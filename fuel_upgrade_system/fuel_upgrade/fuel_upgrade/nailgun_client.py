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
import logging
import requests

from keystoneclient import exceptions
from keystoneclient.v2_0.client import Client as KeystoneClient

logger = logging.getLogger(__name__)


class NailgunClient(object):
    """NailgunClient is a simple wrapper around Nailgun API.

    :param str host: nailgun's host address
    :param (str|int) port: nailgun's port number
    :param str user: user name
    :param str password: user password
    :param str auth_url: authentification url
    :param str tenant_name: tenant name
    """

    api_url = 'http://{host}:{port}/api/v1'

    def __init__(
            self,
            host=None,
            port=None,
            user=None,
            password=None,
            auth_url=None,
            tenant_name=None):

        #: an url to nailgun's restapi service
        self.api_url = self.api_url.format(host=host, port=port)
        #: user name
        self.username = user
        #: user password
        self.password = password
        #: authentification url
        self.auth_url = auth_url
        #: tenant name
        self.tenant_name = tenant_name

    def get_releases(self):
        """Returns a list with all releases.
        """
        r = self.request.get(
            '{api_url}/releases/'.format(api_url=self.api_url))

        if r.status_code not in (200, ):
            r.raise_for_status()
        return r.json()

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
        session = requests.Session()
        token = self.get_token()
        if token:
            session.headers.update({'X-Auth-Token': token})

        return session

    def get_token(self):
        """Retrieves auth token from keystone

        :returns: authentification token

        NOTE(eli): for 5.0.x versions of fuel we don't
        have keystone and fuel access control feature,
        as result this client should work with and without
        authentication, in order to do this, we are
        trying to create Keystone client and in case if
        it fails we don't use authentication
        """
        credentials_are_valid = (
            self.username and
            self.password and
            self.auth_url and
            self.tenant_name)

        if not credentials_are_valid:
            return None

        try:
            keystone_client = KeystoneClient(
                username=self.username,
                password=self.password,
                auth_url=self.auth_url,
                tenant_name=self.tenant_name)

            return keystone_client.auth_token
        except exceptions.ClientException as exc:
            logger.debug('Cannot initialize keystone client: {0}'.format(exc))

        return None
