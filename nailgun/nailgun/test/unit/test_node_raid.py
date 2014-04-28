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

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestRaidHandlers(BaseIntegrationTest):

    def test_get_handler(self):
        resp = self.app.get(reverse('NodeRaidHandler',
                                    kwargs={'node_id': 1}),
                            expect_errors=True,
                            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)


class TestDefaultsRaidHandlers(BaseIntegrationTest):

    def test_get_handler(self):
        resp = self.app.get(reverse('NodeDefaultsRaidHandler',
                                    kwargs={'node_id': 1}),
                            expect_errors=True,
                            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)
