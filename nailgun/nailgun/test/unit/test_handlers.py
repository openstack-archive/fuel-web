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

import json
import urllib

import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import Scope
from nailgun.api.v1.handlers.base import serialize

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


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
            self.assertIn(resp.status_code, [404, 405])
            resp = self.app.delete(test_url, expect_errors=True)
            self.assertIn(resp.status_code, [404, 405])
            resp = self.app.put(
                test_url,
                json.dumps({}),
                expect_errors=True
            )
            self.assertIn(resp.status_code, [404, 405])
            resp = self.app.post(
                test_url,
                json.dumps({}),
                expect_errors=True
            )
            self.assertIn(resp.status_code, [404, 405])

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
                raise BaseHandler.http(
                    status_code=code,
                    msg=message,
                    headers=headers
                )

            self.assertTrue(web.ctx.status.startswith(str(code)))
            self.assertTrue(cm.exception.data, message)

            for header, value in headers.items():
                self.assertIn((header, value), web.ctx.headers)

    def test_content_decorator(self):

        class FakeHandler(BaseHandler):

            @serialize
            def GET(self):
                return {}

            @serialize
            def POST(self):
                return {}

        web.ctx.headers = []
        web.ctx.env = {"HTTP_ACCEPT": "text/html"}

        fake_handler = FakeHandler()
        self.assertRaises(
            web.webapi.UnsupportedMediaType,
            fake_handler.GET
        )

        web.ctx.env = {"HTTP_ACCEPT": "*/*"}
        web.ctx.headers = []
        fake_handler.GET()
        self.assertIn(
            ('Content-Type', 'application/json'),
            web.ctx.headers
        )

        web.ctx.headers = []
        web.ctx.env = {"HTTP_ACCEPT": "application/json"}
        fake_handler.POST()
        self.assertIn(
            # we don't have plain/text serializer right now
            ('Content-Type', 'application/json'),
            web.ctx.headers
        )

    def test_invalid_handler_output(self):

        class FakeHandler(object):

            @handle_errors
            @serialize
            def GET(self):
                return {set([1, 2, 3])}

        fake_handler = FakeHandler()
        web.ctx.env = {"HTTP_ACCEPT": "*/*"}
        web.ctx.headers = []
        self.assertRaises(web.HTTPError, fake_handler.GET)

    def test_get_param_as_set(self):
        urls = ("/hello", "hello")

        class hello(object):
            def GET(self_inner):
                web.header('Content-Type', 'application/json')
                data = BaseHandler.get_param_as_set('test_param',
                                                    delimiter=';')
                return json.dumps(list(data))

        app = web.application(urls, {'hello': hello})
        url = '/hello?test_param=' + urllib.quote('1;4 ; 777; 4;x  ')
        resp = app.request(url)

        self.assertEqual(set(json.loads(resp.data)),
                         set(['1', '4', '777', 'x']))

    def check_get_requested_mime(self, headers, expected_mime):
        urls = ("/hello", "hello")

        class hello(object):
            def GET(self_inner):
                web.header('Content-Type', 'text/plain')
                return BaseHandler.get_requested_mime()

        app = web.application(urls, {'hello': hello})
        resp = app.request('/hello', headers=headers)

        self.assertEqual(resp.data, expected_mime)

    def test_get_requested_mime1(self):
        self.check_get_requested_mime({'ACCEPT': 'text/html'}, 'text/html')

    def test_get_requested_mime2(self):
        self.check_get_requested_mime(
            {'ACCEPT': 'text/plain;q=0.7, text/html;level=1,'}, 'text/plain')

    def test_get_requested_default(self):
        self.check_get_requested_mime({}, 'application/json')

    def test_scope(self):
        # test empty query
        web.ctx.env = {'REQUEST_METHOD': 'GET'}
        scope = Scope()
        self.assertEqual(scope.limit, None)
        self.assertEqual(scope.offset, 0)
        self.assertEqual(scope.order_by, None)
        # test value retrieval from web + order_by cleanup
        q = 'limit=1&offset=5&order_by=-id, timestamp ,   somefield '
        web.ctx.env['QUERY_STRING'] = q
        scope = Scope()
        self.assertEqual(scope.limit, 1)
        self.assertEqual(scope.offset, 5)
        self.assertEqual(set(scope.order_by),
                         set(['-id', 'timestamp', 'somefield']))
        # test incorrect values ignored
        web.ctx.env['QUERY_STRING'] = 'limit=qwe,offset=asd,order_by='
        scope = Scope()
        self.assertEqual(scope.limit, None)
        self.assertEqual(scope.offset, 0)
        self.assertEqual(scope.order_by, None)
        # test constructor with arguments and incorrect order_by
        scope = Scope(1, 2, ', ,,,  ,')
        self.assertEqual(scope.limit, 1)
        self.assertEqual(scope.offset, 2)
        self.assertEqual(scope.order_by, None)
        # offset = 0 if limit = 0
        scope = Scope(0, 5, '')
        self.assertEqual(scope.limit, 0)
        self.assertEqual(scope.offset, 0)
