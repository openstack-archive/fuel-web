#    Copyright 2016 Mirantis, Inc.
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

from nailgun.test.base import BaseTestCase
from nailgun.test.utils import make_mock_extensions
from nailgun.utils import reverse


class TestExtensionHandler(BaseTestCase):

    def test_get_extensions_list(self):
        exts_names = 'ext1', 'ext2'

        with mock.patch('nailgun.api.v1.handlers.extension.get_all_extensions',
                        return_value=make_mock_extensions(exts_names)):

            resp = self.app.get(
                reverse('ExtensionHandler'),
                headers=self.default_headers,
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 2)
