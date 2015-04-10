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

import mock
from oslo_serialization import jsonutils as json
import unittest2

from fuel_package_updates import clients


class TestHTTPClient(unittest2.TestCase):

    @mock.patch('fuel_package_updates.clients.keystoneclient')
    @mock.patch('fuel_package_updates.clients.requests.get')
    def test_perform_request(self, mget, mkeystoneclient):
        url = 'http://some-url.com/'
        keystone_url = 'http://keystone-url.com'
        client = clients.HTTPClient(url, keystone_url, {})

        endpoint = 'clusters/1/attributes'
        client._perform_request('get', endpoint)

        self.assertEqual(mget.call_count, 1)
        self.assertEqual(mget.call_args[0][0], url + endpoint)
        self.assertIn('headers', mget.call_args[1])
        self.assertIn('X-Auth-Token', mget.call_args[1]['headers'])


class TestNailgunClient(unittest2.TestCase):

    def setUp(self):
        self.admin_node_ip = "10.0.0.20"
        self.port = 8000
        self.nailgun_client = clients.NailgunClient(self.admin_node_ip,
                                                    self.port, {})

    @mock.patch('fuel_package_updates.clients.requests.get')
    def test_get_cluster_attributes(self, mget):
        mget.return_value = mock.Mock(status_code=200)
        endpoint = "api/clusters/1/attributes/"
        auth_token = 'token12345678'
        with mock.patch('fuel_package_updates.clients.HTTPClient.token',
                        return_value=auth_token):
            self.nailgun_client.get_cluster_attributes(1)

        get_url = 'http://{ip}:{port}/{endpoint}'.format(
            ip=self.admin_node_ip,
            port=self.port,
            endpoint=endpoint,
        )
        self.assertEqual(get_url, mget.call_args[0][0])

    @mock.patch('fuel_package_updates.clients.requests.put')
    def test_update_cluster_attributes(self, mput):
        mput.return_value = mock.Mock(status_code=200)
        endpoint = "api/clusters/1/attributes/"
        auth_token = 'token12345678'
        data = {'key': 'value'}
        with mock.patch('fuel_package_updates.clients.HTTPClient.token',
                        return_value=auth_token):
            self.nailgun_client.update_cluster_attributes(1, data)

        put_url = 'http://{ip}:{port}/{endpoint}'.format(
            ip=self.admin_node_ip,
            port=self.port,
            endpoint=endpoint,
        )
        self.assertEqual(put_url, mput.call_args[0][0])
        self.assertIn('data', mput.call_args[1])
        self.assertEqual(json.dumps(data), mput.call_args[1]['data'])

    @mock.patch('fuel_package_updates.utils.exit_with_error',
                side_effect=SystemExit)
    @mock.patch('fuel_package_updates.clients.HTTPClient.get')
    def test_http404_error(self, mget, mexit_with_error):
        status_code = 404
        reason = "Not found"
        url = "http://example.com/"
        content = "ERROR"
        mget.return_value = mock.Mock(
            status_code=status_code,
            reason=reason,
            url=url,
            content=content)
        with self.assertRaises(SystemExit):
            self.nailgun_client.get_cluster_attributes(1)

        mexit_with_error.assert_called_with(
            '{0} {1} at {2} with error {3}'.format(status_code, reason,
                                                   url, content))
