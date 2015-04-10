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

import json
import logging
import traceback
import urllib2

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
        self.keystone = None
        self.opener = urllib2.build_opener(urllib2.HTTPHandler)

    def authenticate(self):
        try:
            logger.debug('Initialize keystoneclient with url %s',
                         self.keystone_url)
            self.keystone = keystoneclient(
                auth_url=self.keystone_url, **self.creds)
            # it depends on keystone version, some versions doing auth
            # explicitly some dont, but we are making it explicitly always
            self.keystone.authenticate()
            logger.debug('Authorization token is successfully updated')
        except exceptions.AuthorizationFailure:
            logger.warning(
                'Cant establish connection to keystone with url %s',
                self.keystone_url)

    @property
    def token(self):
        if self.keystone is not None:
            try:
                return self.keystone.auth_token
            except exceptions.AuthorizationFailure:
                logger.warning(
                    'Cant establish connection to keystone with url %s',
                    self.keystone_url)
            except exceptions.Unauthorized:
                logger.warning("Keystone returned unauthorized error, trying "
                               "to pass authentication.")
                self.authenticate()
                return self.keystone.auth_token
        return None

    def get(self, endpoint):
        req = urllib2.Request(self.url + endpoint)
        return self._open(req)

    def post(self, endpoint, data=None, content_type="application/json"):
        if not data:
            data = {}
        logger.info('self url is %s' % self.url)
        req = urllib2.Request(self.url + endpoint, data=json.dumps(data))
        req.add_header('Content-Type', content_type)
        return self._open(req)

    def put(self, endpoint, data=None, content_type="application/json"):
        if not data:
            data = {}
        req = urllib2.Request(self.url + endpoint, data=json.dumps(data))
        req.add_header('Content-Type', content_type)
        req.get_method = lambda: 'PUT'
        return self._open(req)

    def delete(self, endpoint):
        req = urllib2.Request(self.url + endpoint)
        req.get_method = lambda: 'DELETE'
        return self._open(req)

    def _open(self, req):
        try:
            return self._get_response(req)
        except urllib2.HTTPError as e:
            if e.code == 401:
                logger.warning('Authorization failure: {0}'.format(e.reason))
                self.authenticate()
                return self._get_response(req)
            else:
                raise

    def _get_response(self, req):
        if self.token is not None:
            try:
                logger.debug('Set X-Auth-Token to {0}'.format(self.token))
                req.add_header("X-Auth-Token", self.token)
            except exceptions.AuthorizationFailure:
                logger.warning('Failed with auth in http _get_response')
                logger.warning(traceback.format_exc())
        return self.opener.open(req)


class NailgunClient(object):

    def __init__(self, admin_node_ip, port, keystone_creds, **kwargs):
        url = "http://{0}:{1}".format(admin_node_ip, port)
        logger.debug('Initiate Nailgun client with url %s', url)
        self.keystone_url = "http://{0}:5000/v2.0".format(admin_node_ip)
        self._client = HTTPClient(url=url, keystone_url=self.keystone_url,
                                  credentials=keystone_creds,
                                  **kwargs)

    @utils.json_parse
    def _request(self, method, url, attrs=None):
        try:

            if method.lower() == 'get':
                return self._client.get(url)
            elif method.lower() == 'put':
                return self._client.put(url, attrs)

        except urllib2.HTTPError as error:
            if error.code == 404:
                utils.exit_with_error(
                    '{}. Probably cluster with given id do not '
                    'exists or wrong nailgun address has been provided.'
                    '\n{}'.format(error, error.url))
            raise

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

    def environment(self):
        """Environment Model

        :rtype: EnvironmentModel
        """
        return self._environment

    def update_cluster_repos(self,
                             cluster_id,
                             settings=None):
        """Updates a cluster with new settings

        :param cluster_id:
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
