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

from fuel_upgrade import errors
from fuel_upgrade import nailgun_client
from fuel_upgrade.tests import base


class TestNailgunClient(base.BaseTestCase):
    def setUp(self):
        self.nailgun = nailgun_client.NailgunClient('http://127.0.0.1', 8000)

    def test_create_release(self):
        with mock.patch(
            'fuel_upgrade.nailgun_client.utils.post_request'
        ) as post_request:

            # test normal bahavior
            post_request.return_value = ({'id': '42'}, 201)
            response = self.nailgun.create_release({
                'name': 'Havana on Ubuntu 12.04'
            })

            self.assertEqual(response, {'id': '42'})

            # test failed result
            post_request.return_value = ({'id': '42'}, 409)
            self.assertRaises(
                errors.FailedApiCall,
                self.nailgun.create_release,
                {
                    'name': 'Havana on Ubuntu 12.04'
                }
            )

    def test_delete_release(self):
        with mock.patch(
            'fuel_upgrade.nailgun_client.utils.delete_request'
        ) as delete_request:

            # test normal bahavior
            for status in (200, 204):
                delete_request.return_value = ('No Content', status)
                response = self.nailgun.remove_release(42)

                self.assertEqual(response, 'No Content')

            # test failed result
            delete_request.return_value = ('Conflict', 409)
            self.assertRaises(
                errors.FailedApiCall,
                self.nailgun.remove_release,
                42
            )

    def test_create_notification(self):
        with mock.patch(
            'fuel_upgrade.nailgun_client.utils.post_request'
        ) as post_request:
            # test normal bahavior
            post_request.return_value = ({'id': '42'}, 201)
            response = self.nailgun.create_notification({
                'topic': 'release',
                'message': 'New release available!'
            })

            self.assertEqual(response, {'id': '42'})

            # test failed result
            post_request.return_value = ({'id': '42'}, 409)
            self.assertRaises(
                errors.FailedApiCall,
                self.nailgun.create_notification,
                {
                    'topic': 'release',
                    'message': 'New release available!'
                }
            )

    def test_delete_notification(self):
        with mock.patch(
            'fuel_upgrade.nailgun_client.utils.delete_request'
        ) as delete_request:

            # test normal bahavior
            for status in (200, 204):
                delete_request.return_value = ('No Content', status)
                response = self.nailgun.remove_notification(42)

                self.assertEqual(response, 'No Content')

            # test failed result
            delete_request.return_value = ('Conflict', 409)
            self.assertRaises(
                errors.FailedApiCall,
                self.nailgun.remove_notification,
                42
            )
