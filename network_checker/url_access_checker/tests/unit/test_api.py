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

import unittest2

import mock

from url_access_checker import api
import url_access_checker.errors as errors


class TestApi(unittest2.TestCase):

    def setUp(self):
        self.urls = ['url{0}'.format(i) for i in range(10)]
        self.paths = ['file:///tmp/test_api{0}'.format(i) for i in range(10)]

    @mock.patch('requests.get')
    def test_check_urls(self, get_mock):
        response_mock = mock.Mock()
        response_mock.status_code = 200
        get_mock.return_value = response_mock

        check_result = api.check_urls(self.urls)

        self.assertTrue(check_result)

    @mock.patch('requests.get')
    def test_check_urls_fail(self, get_mock):
        response_mock = mock.Mock()
        response_mock.status_code = 404
        get_mock.return_value = response_mock

        with self.assertRaises(errors.UrlNotAvailable):
            api.check_urls(self.urls)

    @mock.patch('os.path.exists')
    def test_check_paths(self, mock_exists):
        mock_exists.return_value = True
        check_result = api.check_urls(self.paths)

        self.assertTrue(check_result)

    @mock.patch('os.path.exists')
    def test_check_paths_fail(self, mock_exists):
        mock_exists.return_value = False
        with self.assertRaises(errors.UrlNotAvailable):
            api.check_urls(self.paths)
