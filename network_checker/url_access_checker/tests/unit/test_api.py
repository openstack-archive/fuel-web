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
import requests_mock

from url_access_checker import api
from url_access_checker import errors


class TestApi(unittest2.TestCase):

    def setUp(self):
        self.urls = ['http://url{0}'.format(i) for i in range(10)]
        self.paths = ['file:///tmp/test_api{0}'.format(i) for i in range(10)]
        self.ftps = ['ftp://url{0}'.format(i) for i in range(10)]

    @requests_mock.Mocker()
    def test_check_urls(self, req_mocker):
        for url in self.urls:
            req_mocker.get(url, status_code=200)

        check_result = api.check_urls(self.urls)

        self.assertTrue(check_result)

    @requests_mock.Mocker()
    def test_check_urls_fail(self, req_mocker):
        for url in self.urls:
            req_mocker.get(url, status_code=404)

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

    @mock.patch('urllib2.urlopen')
    def test_check_ftp(self, _):
        check_result = api.check_urls(self.ftps, timeout=5)
        self.assertTrue(check_result)

    def test_check_ftp_fail(self):
        with self.assertRaises(errors.UrlNotAvailable):
            api.check_urls(self.paths)
