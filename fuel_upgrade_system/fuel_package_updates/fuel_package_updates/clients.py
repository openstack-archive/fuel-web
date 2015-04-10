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

import logging
from oslo_serialization import jsonutils as json
import requests
import urlparse

from keystoneclient import exceptions
from keystoneclient.v2_0 import Client as keystoneclient

from fuel_package_updates import utils

logger = logging.getLogger(__name__)


class HTTPClient(object):

    def __init__(self, url, keystone_url, credentials, **kwargs):
        logger.debug('Initiate HTTPClient with url %s', url)
        self.url = url
        self.keystone_url = keystone_url
        self.creds = dict(credentials, **kwargs)
        self._authenticate()

    def _authenticate(self):
        try:
            logger.debug('Initialize keystoneclient with url %s',
                         self.keystone_url)
            self._keystone = keystoneclient(
                auth_url=self.keystone_url, **self.creds)
            # it depends on keystone version, some versions doing auth
            # explicitly some don't, but we are making it explicitly always
            self._keystone.authenticate()
            logger.debug('Authorization token is successfully updated')
        except exceptions.AuthorizationFailure:
            logger.warning(
                'Cannot establish connection to keystone with url %s',
                self.keystone_url)

    @property
    def token(self):
        try:
            return self._keystone.auth_token
        except exceptions.AuthorizationFailure:
            logger.warning(
                'Cant establish connection to keystone with url %s',
                self.keystone_url)
        except exceptions.Unauthorized:
            logger.warning("Keystone returned unauthorized error, trying "
                           "to pass authentication.")
            self._authenticate()
            return self._keystone.auth_token

    def _perform_request(self, method, endpoint, **kwargs):
        headers = {
            'X-Auth-Token': self.token,
        }
        if kwargs.get('headers'):
            headers.update(kwargs.pop('headers'))

        url = urlparse.urljoin(self.url, endpoint)
        http_method = getattr(requests, method.lower())
        return http_method(url, headers=headers, **kwargs)

    def get(self, endpoint):
        return self._perform_request('get', endpoint)

    def put(self, endpoint, data=None, content_type="application/json"):
        if not data:
            data = {}
        json_data = json.dumps(data)

        headers = {
            'Content-type': content_type,
        }
        return self._perform_request('put', endpoint, data=json_data,
                                     headers=headers)


class NailgunClient(object):

    def __init__(self, admin_node_ip, port, keystone_creds, **kwargs):
        url = "http://{0}:{1}".format(admin_node_ip, port)
        logger.debug('Initiate Nailgun client with url %s', url)
        self.keystone_url = "http://{0}:5000/v2.0".format(admin_node_ip)
        self._client = HTTPClient(url=url, keystone_url=self.keystone_url,
                                  credentials=keystone_creds,
                                  **kwargs)

    def _request(self, method, url, attrs=None):
        if method.lower() == 'get':
            response = self._client.get(url)
        elif method.lower() == 'put':
            response = self._client.put(url, attrs)

        if response.status_code >= 400:
            utils.exit_with_error(
                '{0} {1} at {2} with error {3}'.format(
                    response.status_code, response.reason,
                    response.url, response.content))

        return response.json()

    def get_cluster_attributes(self, cluster_id):
        return self._request(
            "get", "/api/clusters/{0}/attributes/".format(cluster_id))

    def update_cluster_attributes(self, cluster_id, attrs):
        return self._request(
            "put", "/api/clusters/{0}/attributes/".format(cluster_id), attrs)


class FuelWebClient(object):

    def __init__(self, admin_node_ip, port, keystone_creds):
        self.admin_node_ip = admin_node_ip
        self.client = NailgunClient(admin_node_ip, port, keystone_creds)

    def update_cluster_repos(self,
                             cluster_id,
                             settings=None):
        """Updates a cluster with new settings

        :param cluster_id: id of cluster to update
        :param settings:
        """
        if settings is None:
            settings = {}

        attributes = self.client.get_cluster_attributes(cluster_id)

        if 'repo_setup' in attributes['editable']:
            repos_attr = attributes['editable']['repo_setup']['repos']
            repos_attr['value'] = utils.repo_merge(repos_attr['value'],
                                                   settings)

        logger.debug("Try to update cluster "
                     "with next attributes {0}".format(attributes))
        self.client.update_cluster_attributes(cluster_id, attributes)
