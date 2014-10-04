# -*- coding: utf-8 -*-

# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from mock import patch
from nailgun.api.v1.handlers.removed import RemovedIn51Handler as Handler
from nailgun.test.base import BaseIntegrationTest


class TestRemovedIn51Handler(BaseIntegrationTest):
    def assert_resp_ok(self, resp):
        self.assertEqual(resp.status_code, 410)
        self.assertEqual(resp.body, self.body)

    def setUp(self):
        super(TestRemovedIn51Handler, self).setUp()

        self.body = u"Removed in Fuel version 5.1"

        self.args = ('/api/v1/test/res/',)
        # self.args = (reverse(handler),)
        self.kwargs = {
            'headers': self.default_headers,
            'params': {
                'fa': 'ke',
                'pa': 'ra',
                'm': 5
            },
            'expect_errors': True
        }

    @patch('nailgun.api.v1.urls.RemovedIn51Handler', Handler, create=True)
    @patch('nailgun.api.v1.urls.urls', ['/test/res/?$', 'RemovedIn51Handler'])
    def test_get_removed(self):
        resp = self.app.get(*self.args, **self.kwargs)
        self.assert_resp_ok(resp)

    @patch('nailgun.api.v1.urls.RemovedIn51Handler', Handler, create=True)
    @patch('nailgun.api.v1.urls.urls', ['/test/res/?$', 'RemovedIn51Handler'])
    def test_head_removed(self):
        self.kwargs.pop('params')
        resp = self.app.head(*self.args, **self.kwargs)
        self.assert_resp_ok(resp)

    @patch('nailgun.api.v1.urls.RemovedIn51Handler', Handler, create=True)
    @patch('nailgun.api.v1.urls.urls', ['/test/res/?$', 'RemovedIn51Handler'])
    def test_post_removed(self):
        resp = self.app.post(*self.args, **self.kwargs)
        self.assert_resp_ok(resp)

    @patch('nailgun.api.v1.urls.RemovedIn51Handler', Handler, create=True)
    @patch('nailgun.api.v1.urls.urls', ['/test/res/?$', 'RemovedIn51Handler'])
    def test_put_removed(self):
        resp = self.app.put(*self.args, **self.kwargs)
        self.assert_resp_ok(resp)

    @patch('nailgun.api.v1.urls.RemovedIn51Handler', Handler, create=True)
    @patch('nailgun.api.v1.urls.urls', ['/test/res/?$', 'RemovedIn51Handler'])
    def test_delete_removed(self):
        resp = self.app.delete(*self.args, **self.kwargs)
        self.assert_resp_ok(resp)
