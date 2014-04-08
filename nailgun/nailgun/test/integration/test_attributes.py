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

from nailgun import objects

from nailgun.db.sqlalchemy.models import Release
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestAttributes(BaseIntegrationTest):

    def test_attributes_creation(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.env.clusters[0]
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        release = objects.Release.get_by_uid(cluster['current_release_id'])
        self.assertEquals(200, resp.status_code)
        self.assertEquals(
            json.loads(resp.body)['editable'],
            release.attributes_metadata['editable']
        )
        attrs = objects.Cluster.get_attributes(cluster_db)
        self._compare(
            release.attributes_metadata['generated'],
            attrs.generated
        )

    def test_500_if_no_attributes(self):
        cluster = self.env.create_cluster(api=False)
        self.db.delete(cluster.attributes)
        self.db.commit()
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster.id}),
            params=json.dumps({
                'editable': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(500, resp.status_code)

    def test_attributes_update_put(self):
        cluster_id = self.env.create_cluster(api=True)['id']
        cluster_db = self.env.clusters[0]
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=json.dumps({
                'editable': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        attrs = objects.Cluster.get_attributes(cluster_db)
        self.assertEquals("bar", attrs.editable["foo"])
        attrs.editable.pop('foo')
        self.assertEqual(attrs.editable, {})
        # 400 on generated update
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=json.dumps({
                'generated': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(400, resp.status_code)
        # 400 if editable is not dict
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=json.dumps({
                'editable': ["foo", "bar"],
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(400, resp.status_code)

    def test_attributes_update_patch(self):
        cluster_id = self.env.create_cluster(api=True)['id']
        cluster_db = self.env.clusters[0]
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=json.dumps({
                'editable': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        attrs = objects.Cluster.get_attributes(cluster_db)
        self.assertEquals("bar", attrs.editable["foo"])
        attrs.editable.pop('foo')
        self.assertNotEqual(attrs.editable, {})

    def test_get_default_attributes(self):
        cluster = self.env.create_cluster(api=True)
        release = self.db.query(Release).get(
            cluster['current_release_id']
        )
        resp = self.app.put(
            reverse(
                'ClusterAttributesDefaultsHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        self.assertEquals(
            json.loads(resp.body)['editable'],
            release.attributes_metadata['editable']
        )

    def test_attributes_set_defaults(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.env.clusters[0]
        # Change editable attributes.
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=json.dumps({
                'editable': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(200, resp.status_code)
        attrs = objects.Cluster.get_attributes(cluster_db)
        self.assertEquals("bar", attrs.editable["foo"])
        # Set attributes to defaults.
        resp = self.app.put(
            reverse(
                'ClusterAttributesDefaultsHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        release = self.db.query(Release).get(
            cluster['current_release_id']
        )
        self.assertEquals(
            json.loads(resp.body)['editable'],
            release.attributes_metadata['editable']
        )

    def test_attributes_merged_values(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = objects.Cluster.get_by_uid(cluster['id'])
        attrs = objects.Cluster.get_attributes(cluster_db)
        orig_attrs = objects.Attributes.merged_attrs(attrs)
        attrs = objects.Attributes.merged_attrs_values(attrs)
        for group, group_attrs in orig_attrs.iteritems():
            for attr, orig_value in group_attrs.iteritems():
                if group == 'common':
                    value = attrs[attr]
                elif group == 'additional_components':
                    for c, val in group_attrs.iteritems():
                        self.assertIn(c, attrs)
                        if 'value' in val:
                            self.assertEquals(val["value"],
                                              attrs[c]["enabled"])
                    continue
                else:
                    value = attrs[group][attr]
                if isinstance(orig_value, dict) and 'value' in orig_value:
                    self.assertEquals(orig_value['value'], value)
                else:
                    self.assertEquals(orig_value, value)

    def _compare(self, d1, d2):
        if isinstance(d1, dict) and isinstance(d2, dict):
            for s_field, s_value in d1.iteritems():
                if s_field not in d2:
                    raise KeyError()
                self._compare(s_value, d2[s_field])
        elif isinstance(d1, str) or isinstance(d1, unicode):
            if d1 in [u"", ""]:
                self.assertEqual(len(d2), 8)
            else:
                self.assertEqual(d1, d2)
