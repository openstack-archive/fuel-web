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
from StringIO import StringIO
import urllib2

import mock
import unittest2

from fuel_package_updates import clients


class TestHTTPClient(unittest2.TestCase):

    def setUp(self):
        url = 'http://some-url.com/'
        endpoint = 'some-endpoint/'
        self.client = clients.HTTPClient(url, '', {})
        self.request = urllib2.Request(url + endpoint, data=json.dumps({}))

    @mock.patch('fuel_package_updates.clients.HTTPClient.authenticate')
    @mock.patch('fuel_package_updates.clients.HTTPClient._get_response',
                side_effect=urllib2.HTTPError('', 401, '', {}, None))
    def test_open(self, m_get_response, mauthenticate):
        with self.assertRaises(urllib2.HTTPError):
            self.client._open(self.request)

        self.assertEqual(m_get_response.call_count, 2)
        self.assertEqual(mauthenticate.call_count, 1)


class TestNailgunClient(unittest2.TestCase):

    def setUp(self):
        self.admin_node_ip = "10.0.0.20"
        self.port = 8000
        self.nailgun_client = clients.NailgunClient(self.admin_node_ip,
                                                    self.port, {})

    @mock.patch('fuel_package_updates.clients.HTTPClient.get',
                return_value=StringIO("{}"))
    def test_get_cluster_attrubutes(self, m_get):
        endpoint = "/api/clusters/1/attributes/"
        self.nailgun_client.get_cluster_attributes(1)

        m_get.assert_called_with(endpoint)

    @mock.patch('fuel_package_updates.clients.HTTPClient.put',
                return_value=StringIO("{}"))
    def test_put_cluster_attrubutes(self, m_put):
        endpoint = "/api/clusters/1/attributes/"
        data = {'key': 'value'}

        self.nailgun_client.update_cluster_attributes(1, data)
        m_put.assert_called_with(endpoint, data)

    @mock.patch('fuel_package_updates.clients.HTTPClient.get',
                side_effect=urllib2.HTTPError('', 404, '', {}, StringIO()))
    @mock.patch('fuel_package_updates.utils.exit_with_error',
                side_effect=SystemExit)
    def test_http404_error(self, mexit_with_error, mget):
        with self.assertRaises(SystemExit):
            self.nailgun_client.get_cluster_attributes(1)

        message = str(mexit_with_error.call_args)
        self.assertIn('HTTP Error 404', message)
        self.assertIn('Probably cluster with given id do not exists '
                      'or wrong nailgun address has been provided',
                      message)
