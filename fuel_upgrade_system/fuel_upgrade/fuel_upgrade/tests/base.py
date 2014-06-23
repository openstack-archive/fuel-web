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

try:
    from unittest.case import TestCase
except ImportError:
    # Required for python 2.6
    from unittest2.case import TestCase

from StringIO import StringIO

import mock
import requests

from fuel_upgrade import config


class FakeFile(StringIO):
    """It's a fake file which returns StringIO
    when file opens with 'with' statement.

    NOTE(eli): We cannot use mock_open from mock library
    here, because it hangs when we use 'with' statement,
    and when we want to read file by chunks.
    """
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class BaseTestCase(TestCase):
    """Base class for test cases
    """

    def method_was_not_called(self, method):
        """Checks that mocked method was not called
        """
        self.assertEqual(method.call_count, 0)

    def called_once(self, method):
        """Checks that mocked method was called once
        """
        self.assertEqual(method.call_count, 1)

    def called_times(self, method, count):
        """Checks that mocked method was called `count` times
        """
        self.assertEqual(method.call_count, count)

    @property
    @mock.patch('fuel_upgrade.config.get_version_from_config',
                side_effect=['0', '9999'])
    @mock.patch('fuel_upgrade.config.from_fuel_version', return_value='0')
    @mock.patch('fuel_upgrade.config.read_yaml_config',
                return_value={'ADMIN_NETWORK': {'ipaddress': '0.0.0.0'}})
    def fake_config(self, _, __, ___):
        update_path = '/tmp/upgrade_path'
        conf = config.build_config(update_path)

        conf.astute = {
            'ADMIN_NETWORK': {
                'ipaddress': '0.0.0.0'
            }
        }

        return conf

    def mock_open(self, text, filename='some.yaml'):
        """Mocks builtin open function.

        Usage example:

            with mock.patch(
                '__builtin__.open',
                self.mock_open('file content')
            ):
                # call some methods that are used open() to read some
                # stuff internally
        """
        fileobj = FakeFile(text)
        setattr(fileobj, 'name', filename)
        return mock.MagicMock(return_value=fileobj)

    def mock_requests_response(self, status_code, body):
        """Creates a response object with custom status code and body.
        """
        rv = requests.Response()
        rv.status_code = status_code
        rv.encoding = 'utf-8'
        rv.raw = FakeFile(body)
        return rv
