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

from mock import Mock
from mock import mock_open
from mock import patch

from contextlib import nested

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestVersionHandler(BaseIntegrationTest):

    @patch('nailgun.api.v1.handlers.version.settings.VERSION', {
        'release': '0.1b',
        'nailgun_sha': '12345',
        "astute_sha": "Unknown build",
        "fuellib_sha": "Unknown build",
        "ostf_sha": "Unknown build",
    })
    def test_version_handler(self):
        with nested(
            patch(
                'nailgun.utils.glob.glob',
                Mock(return_value=["test.yaml"])
            ),
            patch(
                '__builtin__.open',
                mock_open(read_data='test_data'),
                create=True
            )
        ):
            resp = self.app.get(
                reverse('VersionHandler'),
                headers=self.default_headers
            )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(
            resp.json_body,
            {
                "release": "0.1b",
                "nailgun_sha": "12345",
                "astute_sha": "Unknown build",
                "fuellib_sha": "Unknown build",
                "ostf_sha": "Unknown build",
                "auth_required": True,
                "release_versions": {
                    "test": "test_data"
                }
            }
        )
