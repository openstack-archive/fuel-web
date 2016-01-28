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

from nailgun.db.sqlalchemy.models.cluster_plugin_link import ClusterPluginLink
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse
from oslo_serialization import jsonutils


class TestHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestHandlers, self).setUp()
        self.cluster = self.env.create_cluster(api=False)
        self.cluster_plugin_link = self.env \
            .create_cluster_plugin_link(cluster_id=self.cluster.id)

    def test_cluster_plugin_link_update(self):
        cluster_plugin_link_update = {
            'title': 'new title 2',
            'description': 'new description 2'
        }

        resp = self.app.put(
            reverse(
                'ClusterPluginLinkHandler',
                kwargs={'cluster_id': self.cluster['id'],
                        'obj_id': self.cluster_plugin_link.id}
            ),
            jsonutils.dumps(cluster_plugin_link_update),
            headers=self.default_headers
        )
        self.assertEqual(self.cluster_plugin_link.id, resp.json_body['id'])
        self.assertEqual('new title 2', resp.json_body['title'])
        self.assertEqual('new description 2', resp.json_body['description'])
        self.assertEqual(self.cluster_plugin_link.url, resp.json_body['url'])

    def test_cluster_plugin_link_get_with_cluster(self):
        resp = self.app.get(
            reverse(
                'ClusterPluginLinkHandler',
                kwargs={'cluster_id': self.cluster['id'],
                        'obj_id': self.cluster_plugin_link.id}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(self.cluster_plugin_link.id, resp.json_body['id'])
        self.assertEqual(self.cluster_plugin_link.title,
                         resp.json_body['title'])
        self.assertEqual(self.cluster_plugin_link.url, resp.json_body['url'])
        self.assertEqual(self.cluster_plugin_link.description,
                         resp.json_body['description'])
        self.assertEqual(self.cluster_plugin_link.hidden,
                         resp.json_body['hidden'])

    def test_cluster_plugin_link_not_found(self):
        resp = self.app.get(
            reverse(
                'ClusterPluginLinkHandler',
                kwargs={'cluster_id': self.cluster['id'],
                        'obj_id': self.cluster_plugin_link.id + 1}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(404, resp.status_code)

    def test_cluster_plugin_link_fail_duplicate(self):
        self.env.create_cluster_plugin_link(
            cluster_id=self.cluster.id,
            url='http://uniq1.com'
        )
        existing_plugin_link2 = self.env.create_cluster_plugin_link(
            cluster_id=self.cluster.id,
            url='http://uniq2.com'
        )

        resp = self.app.put(
            reverse(
                'ClusterPluginLinkHandler',
                kwargs={'cluster_id': self.cluster['id'],
                        'obj_id': existing_plugin_link2.id}
            ),
            jsonutils.dumps({'url': 'http://uniq1.com'}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(409, resp.status_code)

    def test_cluster_plugin_link_delete(self):
        resp = self.app.delete(
            reverse(
                'ClusterPluginLinkHandler',
                kwargs={'cluster_id': self.cluster['id'],
                        'obj_id': self.cluster_plugin_link.id}
            ),
            headers=self.default_headers,
        )
        self.assertEqual(204, resp.status_code)

        d_e_query = self.db.query(ClusterPluginLink) \
            .filter_by(cluster_id=self.cluster.id)
        self.assertEquals(d_e_query.count(), 0)

    def test_cluster_plugin_link_patch(self):
        cluster_plugin_link_update = {
            'title': 'new title 3',
            'description': 'new description 3',
            'hidden': True
        }

        resp = self.app.patch(
            reverse(
                'ClusterPluginLinkHandler',
                kwargs={'cluster_id': self.cluster['id'],
                        'obj_id': self.cluster_plugin_link.id}
            ),
            jsonutils.dumps(cluster_plugin_link_update),
            headers=self.default_headers
        )
        self.assertEqual(self.cluster_plugin_link.id, resp.json_body['id'])
        self.assertEqual('new title 3', resp.json_body['title'])
        self.assertEqual('new description 3', resp.json_body['description'])
        self.assertEqual(self.cluster_plugin_link.url, resp.json_body['url'])
        self.assertEqual(True, resp.json_body['hidden'])
