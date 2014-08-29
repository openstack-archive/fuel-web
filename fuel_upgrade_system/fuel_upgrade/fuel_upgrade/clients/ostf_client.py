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

import logging

from fuel_upgrade.clients import KeystoneClient

logger = logging.getLogger(__name__)


class OSTFClient(object):
    """OSTFClient is a simple wrapper around OSTF API.

    :param str host: ostf's host address
    :param (str|int) port: ostf's port number
    :param dict keystone_credentials: keystone credentials where
                                     `username` is user name
                                     `password` is user password
                                     `auth_url` authentification url
                                     `tenant_name` tenant name
    """

    api_url = 'http://{host}:{port}'

    def __init__(self, host=None, port=None, keystone_credentials={}):
        #: an url to nailgun's restapi service
        self.api_url = self.api_url.format(host=host, port=port)
        #: keystone credentials for authentification
        self.keystone_client = KeystoneClient(**keystone_credentials)

    @property
    def request(self):
        """Creates authentification session if required

        :returns: :class:`requests.Session` object
        """
        return self.keystone_client.request

    def get(self, path):
        """Retrieve list of tasks from nailgun

        :returns: list of tasks
        """
        result = self.request.get('{api_url}{path}'.format(
            api_url=self.api_url, path=path))

        return result
