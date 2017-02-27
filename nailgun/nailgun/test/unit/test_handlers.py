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
from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import Pagination
from nailgun.api.v1.handlers.base import serialize

from nailgun.objects import NodeCollection

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

    def test_removed_urls(self):
        urls = {
            'RemovedIn51RedHatAccountHandler': {'obj_id', 1},
            'RemovedIn51RedHatSetupHandler': {'obj_id', 1},
            'RemovedIn10VmwareAttributesDefaultsHandler': {'cluster_id': 1},
            'RemovedIn10VmwareAttributesHandler': {'cluster_id': 1},
        }
        for handler in urls:
            test_url = reverse(handler, urls[handler])
            resp = self.app.get(test_url, expect_errors=True)
            self.assertEqual(resp.status_code, 410)

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

    def test_pagination_class(self):
        # test empty query
        web.ctx.env = {'REQUEST_METHOD': 'GET'}
        pagination = Pagination()
        self.assertEqual(pagination.limit, None)
        self.assertEqual(pagination.offset, None)
        self.assertEqual(pagination.order_by, None)
        # test value retrieval from web + order_by cleanup
        q = 'limit=1&offset=5&order_by=-id, timestamp ,   somefield '
        web.ctx.env['QUERY_STRING'] = q
        pagination = Pagination()
        self.assertEqual(pagination.limit, 1)
        self.assertEqual(pagination.offset, 5)
        self.assertEqual(set(pagination.order_by),
                         set(['-id', 'timestamp', 'somefield']))
        # test incorrect values raise 400
        web.ctx.env['QUERY_STRING'] = 'limit=qwe'
        self.assertRaises(web.HTTPError, Pagination)
        web.ctx.env['QUERY_STRING'] = 'offset=asd'
        self.assertRaises(web.HTTPError, Pagination)
        web.ctx.env['QUERY_STRING'] = 'limit='
        self.assertRaises(web.HTTPError, Pagination)
        web.ctx.env['QUERY_STRING'] = 'offset=-2'
        self.assertRaises(web.HTTPError, Pagination)
        # test constructor, limit = 0 -> 0, offset '0' -> 0, bad order_by
        pagination = Pagination(0, '0', ', ,,,  ,')
        self.assertEqual(pagination.limit, 0)
        self.assertEqual(pagination.offset, 0)
        self.assertEqual(pagination.order_by, None)

    def test_pagination_of_node_collection(self):
        def assert_pagination_and_cont_rng(q, cr, sz, first, last, ttl, valid):
            self.assertEqual(q.count(), sz)
            self.assertEqual(cr.first, first)
            self.assertEqual(cr.last, last)
            self.assertEqual(cr.total, ttl)
            self.assertEqual(cr.valid, valid)

        self.env.create_nodes(5)
        # test pagination limited to 2 first items
        pagination = Pagination(limit=2)
        q, cr = NodeCollection.scope(pagination)
        assert_pagination_and_cont_rng(q, cr, 2, 1, 2, 5, True)
        # test invalid pagination
        pagination = Pagination(offset=5)
        q, cr = NodeCollection.scope(pagination)
        assert_pagination_and_cont_rng(q, cr, 0, 0, 0, 5, False)
        # test limit=0, offset ignored
        pagination = Pagination(limit=0, offset=999)
        q, cr = NodeCollection.scope(pagination)
        assert_pagination_and_cont_rng(q, cr, 0, 0, 0, 5, True)
        # test limit+offset+order_by
        pagination = Pagination(limit=3, offset=1, order_by='-id')
        q, cr = NodeCollection.scope(pagination)
        assert_pagination_and_cont_rng(q, cr, 3, 2, 4, 5, True)
        ids = sorted([i.id for i in self.env.nodes])
        n = q.all()
        self.assertEqual(n[0].id, ids[3])
        self.assertEqual(n[1].id, ids[2])
        self.assertEqual(n[2].id, ids[1])

    def test_collection_handler(self):
        FakeHandler = CollectionHandler
        # setting a collection is mandatory, CollectionHandler is not ready
        # to use "as-is"
        FakeHandler.collection = NodeCollection
        urls = ("/collection_test", "collection_test")
        app = web.application(urls, {'collection_test': FakeHandler})
        resp = app.request(urls[0])
        self.assertEqual(resp.status, '200 OK')

    def test_content_range_header(self):
        self.env.create_nodes(5)
        FakeHandler = CollectionHandler
        FakeHandler.collection = NodeCollection
        urls = ("/collection_test", "collection_test")
        app = web.application(urls, {'collection_test': FakeHandler})
        # test paginated query
        resp = app.request("/collection_test?limit=3&offset=1")
        self.assertEqual(resp.status, '200 OK')
        self.assertIn('Content-Range', resp.headers)
        self.assertEqual(resp.headers['Content-Range'], 'objects 2-4/5')
        # test invalid range (offset = 6 >= number of nodes ---> no data)
        resp = app.request("/collection_test?limit=3&offset=5&order_by=id")
        self.assertEqual(resp.status, '416 Range Not Satisfiable')
