# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import base64
from mock import patch

from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseTestCase
from nailgun.test.base import reverse


class TestFuelKeyHandler(BaseTestCase):

    @patch('nailgun.api.v1.handlers.version.settings.VERSION', {
        'release': '0.1',
        'nailgun_sha': '12345'
    })
    @patch('nailgun.api.v1.handlers.version.settings.FUEL_KEY', 'uuid')
    def test_version_handler(self):
        resp = self.app.get(
            reverse('FuelKeyHandler'),
            headers=self.default_headers
        )
        fuel_release = "0.1"
        key_data = {
            "sha": "12345",
            "release": fuel_release,
            "uuid": "uuid"
        }
        signature = base64.b64encode(jsonutils.dumps(key_data))
        key_data["signature"] = signature

        self.assertEqual(200, resp.status_code)

        response = resp.json_body
        self.assertEqual(
            response,
            {"key": base64.b64encode(jsonutils.dumps(key_data))}
        )
        resp_data = jsonutils.loads(base64.b64decode(response["key"]))
        self.assertEqual(resp_data["release"], fuel_release)
