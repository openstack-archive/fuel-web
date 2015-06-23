# -*- coding: utf-8 -*-

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

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestTracking(BaseIntegrationTest):
    """This set of tests checks fake behaviour
    for tracking and proper handling of exceptions
    if using real requests
    """

    def test_get_registration_form(self):
        with mock.patch(
            'nailgun.api.v1.handlers.registration.'
            'FuelTrackingManager.FAKE_MODE',
            True
        ):
            resp = self.app.get(
                reverse('FuelRegistrationForm'),
                expect_errors=False,
                headers=self.default_headers
            )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("credentials", resp.json_body)

    def test_post_registration_form(self):
        with mock.patch(
            'nailgun.api.v1.handlers.registration.'
            'FuelTrackingManager.FAKE_MODE',
            True
        ):
            resp = self.app.get(
                reverse('FuelRegistrationForm'),
                expect_errors=False,
                headers=self.default_headers
            )
            resp = self.app.post(
                reverse('FuelRegistrationForm'),
                resp.body,
                expect_errors=False,
                headers=self.default_headers
            )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("name", resp.json_body)
        self.assertIn("email", resp.json_body)
        self.assertIn("company", resp.json_body)

    def test_post_login_form(self):
        with mock.patch(
            'nailgun.api.v1.handlers.registration.'
            'FuelTrackingManager.FAKE_MODE',
            True
        ):
            resp = self.app.get(
                reverse('FuelLoginForm'),
                expect_errors=False,
                headers=self.default_headers
            )
            resp = self.app.post(
                reverse('FuelLoginForm'),
                resp.body,
                expect_errors=False,
                headers=self.default_headers
            )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("name", resp.json_body)
        self.assertIn("email", resp.json_body)
        self.assertIn("company", resp.json_body)

    def test_failed_to_access(self):
        with mock.patch(
            'nailgun.utils.tracking.requests.get'
        ) as mocked_get:
            mocked_get.side_effect = Exception("Hope is lost")
            resp = self.app.get(
                reverse('FuelRegistrationForm'),
                expect_errors=True,
                headers=self.default_headers
            )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body["message"],
            "Failed to reach external server"
        )

    def test_tracking_400(self):
        with mock.patch(
            'nailgun.utils.tracking.requests.get'
        ) as mocked_get:
            mocked_get.return_value = type(
                'FakeResponse',
                (),
                {'status_code': 400}
            )
            resp = self.app.get(
                reverse('FuelRegistrationForm'),
                expect_errors=True,
                headers=self.default_headers
            )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body["message"],
            "Invalid response code received from external server: 400"
        )
