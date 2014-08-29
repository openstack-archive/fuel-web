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

import mock
import requests

from fuel_upgrade.clients import NailgunClient
from fuel_upgrade.tests import base


class TestNailgunClient(base.BaseTestCase):

    def setUp(self):
        mock_keystone = mock.MagicMock()
        self.mock_request = mock_keystone.request
        with mock.patch(
                'fuel_upgrade.clients.nailgun_client.KeystoneClient',
                return_value=mock_keystone):
            self.nailgun = NailgunClient('127.0.0.1', 8000)

    def test_create_release(self):
        # test normal bahavior
        self.mock_request.post.return_value = self.mock_requests_response(
            201, '{ "id": "42" }')

        response = self.nailgun.create_release({
            'name': 'Havana on Ubuntu 12.04'})

        self.assertEqual(response, {'id': '42'})

        # test failed result
        self.mock_request.post.return_value.status_code = 409
        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.create_release,
            {'name': 'Havana on Ubuntu 12.04'})

    def test_delete_release(self):
        # test normal bahavior
        for status in (200, 204):
            self.mock_request.delete.return_value = \
                self.mock_requests_response(status, 'No Content')
            response = self.nailgun.remove_release(42)
            self.assertEqual(response, 'No Content')

        # test failed result
        self.mock_request.delete.return_value = self.mock_requests_response(
            409, 'Conflict')

        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.remove_release,
            42)

    def test_create_notification(self):
        # test normal bahavior
        self.mock_request.post.return_value = self.mock_requests_response(
            201,
            '{ "id": "42" }')

        response = self.nailgun.create_notification({
            'topic': 'release',
            'message': 'New release available!'})

        self.assertEqual(response, {'id': '42'})

        # test failed result
        self.mock_request.post.return_value.status_code = 409
        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.create_notification,
            {'topic': 'release',
             'message': 'New release available!'})

    def test_delete_notification(self):
        # test normal bahavior
        for status in (200, 204):
            self.mock_request.delete.return_value = \
                self.mock_requests_response(status, 'No Content')
            response = self.nailgun.remove_notification(42)
            self.assertEqual(response, 'No Content')

        # test failed result
        self.mock_request.delete.return_value = self.mock_requests_response(
            409, 'Conflict')

        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.remove_notification,
            42)

    def test_get_tasks(self):
        # test positive cases
        self.mock_request.get.return_value = self.mock_requests_response(
            200, '[1,2,3]')
        response = self.nailgun.get_tasks()
        self.assertEqual(response, [1, 2, 3])

        # test negative cases
        self.mock_request.get.return_value = self.mock_requests_response(
            502, 'Bad gateway')

        self.assertRaises(
            requests.exceptions.HTTPError, self.nailgun.get_tasks)
