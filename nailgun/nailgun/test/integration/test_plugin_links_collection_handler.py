# -*- coding: utf-8 -*-

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

from oslo_serialization import jsonutils

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestAssignmentHandlers(BaseIntegrationTest):
    def setUp(self):
        super(TestAssignmentHandlers, self).setUp()
        self.plugin = self.env.create_plugin()
        self.link_data = {
            'title': 'test title',
            'url': 'http://test.com/url',
            'description': 'short description',
            'hidden': False,
        }

    def test_plugin_links_list_empty(self):
        resp = self.app.get(
            reverse(
                'PluginLinkCollectionHandler',
                kwargs={'plugin_id': self.plugin['id']}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual([], resp.json_body)

    def test_plugin_link_creation(self):
        resp = self.app.post(
            reverse(
                'PluginLinkCollectionHandler',
                kwargs={'plugin_id': self.plugin['id']}
            ),
            params=jsonutils.dumps(self.link_data),
            headers=self.default_headers
        )
        self.assertEqual(201, resp.status_code)

        plugin_link = self.env.plugins[0].links[0]
        self.assertEqual(self.link_data['title'], plugin_link.title)
        self.assertEqual(self.link_data['url'], plugin_link.url)
        self.assertEqual(self.link_data['hidden'], plugin_link.hidden)
        self.assertEqual(
            self.link_data['description'],
            plugin_link.description
        )

    def test_plugin_link_creation_fail_duplicate(self):
        self.env.create_plugin_link(
            plugin_id=self.plugin.id,
            url='http://uniq1.com'
        )
        resp = self.app.post(
            reverse(
                'PluginLinkCollectionHandler',
                kwargs={
                    'plugin_id': self.plugin['id']
                }
            ),
            params=jsonutils.dumps({
                'title': 'My Plugin',
                'url': 'http://uniq1.com'
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(409, resp.status_code)

    def test_plugin_link_fail_creation(self):
        resp = self.app.post(
            reverse(
                'PluginLinkCollectionHandler',
                kwargs={'plugin_id': self.plugin['id']}
            ),
            jsonutils.dumps({
                'title': self.link_data['title'],
                'description': self.link_data['description']
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertItemsEqual([], self.env.plugins[0].links)
