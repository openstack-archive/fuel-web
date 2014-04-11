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

from fuel_upgrade import nailgun_client
from fuel_upgrade.tests import base


class TestNailgunClient(base.BaseTestCase):
    def setUp(self):
        self.nailgun = nailgun_client.NailgunClient('http://127.0.0.1', 8000)

    @mock.patch('fuel_upgrade.nailgun_client.requests.post')
    def test_create_release(self, post_request):
        # test normal bahavior
        post_request.return_value = self.mock_requests_response(
            201,
            '{ "id": "42" }'
        )

        response = self.nailgun.create_release({
            'name': 'Havana on Ubuntu 12.04'
        })

        self.assertEqual(response, {'id': '42'})

        # test failed result
        post_request.return_value.status_code = 409
        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.create_release,
            {
                'name': 'Havana on Ubuntu 12.04'
            }
        )

    @mock.patch('fuel_upgrade.nailgun_client.requests.delete')
    def test_delete_release(self, delete_request):
        # test normal bahavior
        for status in (200, 204):
            delete_request.return_value = self.mock_requests_response(
                status, 'No Content'
            )
            response = self.nailgun.remove_release(42)
            self.assertEqual(response, 'No Content')

        # test failed result
        delete_request.return_value = self.mock_requests_response(
            409, 'Conflict'
        )
        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.remove_release,
            42
        )

    @mock.patch('fuel_upgrade.nailgun_client.requests.post')
    def test_create_notification(self, post_request):
        # test normal bahavior
        post_request.return_value = self.mock_requests_response(
            201,
            '{ "id": "42" }'
        )
        response = self.nailgun.create_notification({
            'topic': 'release',
            'message': 'New release available!'
        })

        self.assertEqual(response, {'id': '42'})

        # test failed result
        post_request.return_value.status_code = 409
        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.create_notification,
            {
                'topic': 'release',
                'message': 'New release available!'
            }
        )

    @mock.patch('fuel_upgrade.nailgun_client.requests.delete')
    def test_delete_notification(self, delete_request):
        # test normal bahavior
        for status in (200, 204):
            delete_request.return_value = self.mock_requests_response(
                status, 'No Content'
            )
            response = self.nailgun.remove_notification(42)

            self.assertEqual(response, 'No Content')

        # test failed result
        delete_request.return_value = self.mock_requests_response(
            409, 'Conflict'
        )
        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.remove_notification,
            42
        )
