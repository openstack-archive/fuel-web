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
from keystoneclient import exceptions


class TestNailgunClient(base.BaseTestCase):
    def setUp(self):
        self.nailgun = nailgun_client.NailgunClient('http://127.0.0.1', 8000)

    @mock.patch('fuel_upgrade.nailgun_client.requests.Session.post')
    def test_create_release(self, post):
        # test normal bahavior
        post.return_value = self.mock_requests_response(
            201, '{ "id": "42" }')

        response = self.nailgun.create_release({
            'name': 'Havana on Ubuntu 12.04'})

        self.assertEqual(response, {'id': '42'})

        # test failed result
        post.return_value.status_code = 409
        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.create_release,
            {'name': 'Havana on Ubuntu 12.04'})

    @mock.patch('fuel_upgrade.nailgun_client.requests.Session.delete')
    def test_delete_release(self, delete):
        # test normal bahavior
        for status in (200, 204):
            delete.return_value = self.mock_requests_response(
                status, 'No Content')
            response = self.nailgun.remove_release(42)
            self.assertEqual(response, 'No Content')

        # test failed result
        delete.return_value = self.mock_requests_response(409, 'Conflict')

        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.remove_release,
            42)

    @mock.patch('fuel_upgrade.nailgun_client.requests.Session.post')
    def test_create_notification(self, post):
        # test normal bahavior
        post.return_value = self.mock_requests_response(
            201,
            '{ "id": "42" }')

        response = self.nailgun.create_notification({
            'topic': 'release',
            'message': 'New release available!'})

        self.assertEqual(response, {'id': '42'})

        # test failed result
        post.return_value.status_code = 409
        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.create_notification,
            {'topic': 'release',
             'message': 'New release available!'})

    @mock.patch('fuel_upgrade.nailgun_client.requests.Session.delete')
    def test_delete_notification(self, delete):
        # test normal bahavior
        for status in (200, 204):
            delete.return_value = self.mock_requests_response(
                status, 'No Content')
            response = self.nailgun.remove_notification(42)
            self.assertEqual(response, 'No Content')

        # test failed result
        delete.return_value = self.mock_requests_response(409, 'Conflict')

        self.assertRaises(
            requests.exceptions.HTTPError,
            self.nailgun.remove_notification,
            42)

    @mock.patch('fuel_upgrade.nailgun_client.requests.Session.get')
    def test_get_tasks(self, get):
        # test positive cases
        get.return_value = self.mock_requests_response(200, '[1,2,3]')
        response = self.nailgun.get_tasks()
        self.assertEqual(response, [1, 2, 3])

        # test negative cases
        get.return_value = self.mock_requests_response(502, 'Bad gateway')

        self.assertRaises(
            requests.exceptions.HTTPError, self.nailgun.get_tasks)


class TestNailgunClientWithAuthentification(base.BaseTestCase):

    def setUp(self):
        self.credentials = {
            'username': 'some_user',
            'password': 'some_password',
            'auth_url': 'http://127.0.0.1:5000/v2',
            'tenant_name': 'some_tenant'}

        self.nailgun = nailgun_client.NailgunClient(
            'http://127.0.0.1',
            8000,
            keystone_credentials=self.credentials)

    @mock.patch('fuel_upgrade.nailgun_client.KeystoneClient')
    @mock.patch('fuel_upgrade.nailgun_client.requests.Session')
    def test_makes_authenticated_requests(self, session, keystone):
        keystone.return_value.auth_token = 'auth_token'
        self.nailgun.request.get('http://some.url/path')
        session.return_value.headers.update.assert_called_once_with(
            {'X-Auth-Token': 'auth_token'})

    @mock.patch('fuel_upgrade.nailgun_client.requests.Session')
    @mock.patch('fuel_upgrade.nailgun_client.KeystoneClient',
                side_effect=exceptions.ConnectionError('a'))
    def test_does_not_fail_without_keystone(self, keystone, _):
        self.nailgun.request.get('http://some.url/path')
        keystone.assert_called_once_with(**self.credentials)
        self.assertEqual(self.nailgun.get_token(), None)
