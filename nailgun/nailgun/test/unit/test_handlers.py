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

import web

from nailgun.api.v1.handlers.base import BaseHandler

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):
    def test_all_api_urls_404_or_405(self):
        urls = {
            'ClusterHandler': {'obj_id': 1},
            'NodeHandler': {'obj_id': 1},
            'ReleaseHandler': {'obj_id': 1},
        }
        for handler in urls:
            test_url = reverse(handler, urls[handler])
            resp = self.app.get(test_url, expect_errors=True)
            self.assertTrue(resp.status_code in [404, 405])
            resp = self.app.delete(test_url, expect_errors=True)
            self.assertTrue(resp.status_code in [404, 405])
            resp = self.app.put(test_url, expect_errors=True)
            self.assertTrue(resp.status_code in [404, 405])
            resp = self.app.post(test_url, expect_errors=True)
            self.assertTrue(resp.status_code in [404, 405])

    def test_http_response(self):
        web.ctx.headers = []

        http_codes = (
            (200, 'ok'),
            (201, 'created'),
            (202, 'accepted'),
            (204, 'no content'),

            (400, 'bad request :('),
            (401, 'unauthorized'),
            (403, 'forbidden'),
            (404, 'not found, try again'),
            (405, 'no method'),
            (406, 'unacceptable'),
            (409, 'ooops, conflict'),
            (415, 'unsupported media type'),

            (500, 'internal problems'),
        )

        headers = {
            'Content-Type': 'application/json',
            'ETag': '737060cd8c284d8af7ad3082f209582d',
        }

        # test response status code and message
        for code, message in http_codes:
            with self.assertRaises(web.HTTPError) as cm:
                raise BaseHandler.http(code, message, headers)

            self.assertTrue(web.ctx.status.startswith(str(code)))
            self.assertTrue(cm.exception.data, message)

            for header, value in headers.items():
                self.assertIn((header, value), web.ctx.headers)
