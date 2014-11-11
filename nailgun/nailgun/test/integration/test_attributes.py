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

import six

from nailgun import objects

from nailgun.db.sqlalchemy.models import Release
from nailgun.openstack.common import jsonutils
from nailgun.settings import settings
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
        release = objects.Release.get_by_uid(cluster['release_id'])
        self.assertEqual(200, resp.status_code)
        self._compare_editable(
            release.attributes_metadata['editable'],
            resp.json_body['editable']
        )
        attrs = objects.Cluster.get_attributes(cluster_db)
        self._compare_generated(
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
            params=jsonutils.dumps({
                'editable': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(500, resp.status_code)

    def test_attributes_update_put(self):
        cluster_id = self.env.create_cluster(api=True)['id']
        cluster_db = self.env.clusters[0]
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=jsonutils.dumps({
                'editable': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        attrs = objects.Cluster.get_attributes(cluster_db)
        self.assertEqual("bar", attrs.editable["foo"])
        attrs.editable.pop('foo')
        self.assertEqual(attrs.editable, {})
        # 400 on generated update
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=jsonutils.dumps({
                'generated': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        # 400 if editable is not dict
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=jsonutils.dumps({
                'editable': ["foo", "bar"],
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    def test_attributes_update_patch(self):
        cluster_id = self.env.create_cluster(api=True)['id']
        cluster_db = self.env.clusters[0]
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            params=jsonutils.dumps({
                'editable': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        attrs = objects.Cluster.get_attributes(cluster_db)
        self.assertEqual("bar", attrs.editable["foo"])
        attrs.editable.pop('foo')
        self.assertNotEqual(attrs.editable, {})

    def test_get_default_attributes(self):
        cluster = self.env.create_cluster(api=True)
        release = self.db.query(Release).get(
            cluster['release_id']
        )
        resp = self.app.put(
            reverse(
                'ClusterAttributesDefaultsHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self._compare_editable(
            release.attributes_metadata['editable'],
            resp.json_body['editable']
        )

    def test_attributes_set_defaults(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.env.clusters[0]
        # Change editable attributes.
        resp = self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {
                    "foo": "bar"
                },
            }),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(200, resp.status_code)
        attrs = objects.Cluster.get_attributes(cluster_db)
        self.assertEqual("bar", attrs.editable["foo"])
        # Set attributes to defaults.
        resp = self.app.put(
            reverse(
                'ClusterAttributesDefaultsHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        release = self.db.query(Release).get(
            cluster['release_id']
        )
        self._compare_editable(
            release.attributes_metadata['editable'],
            resp.json_body['editable']
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
                            self.assertEqual(val["value"],
                                             attrs[c]["enabled"])
                    continue
                else:
                    value = attrs[group][attr]
                if isinstance(orig_value, dict) and 'value' in orig_value:
                    self.assertEqual(orig_value['value'], value)
                else:
                    self.assertEqual(orig_value, value)

    def _compare_generated(self, d1, d2):
        if isinstance(d1, dict) and isinstance(d2, dict):
            for s_field, s_value in d1.iteritems():
                if s_field not in d2:
                    raise KeyError()
                self._compare_generated(s_value, d2[s_field])
        elif isinstance(d1, str) or isinstance(d1, unicode):
            if d1 in [u"", ""]:
                self.assertEqual(len(d2), 8)
            else:
                self.assertEqual(d1, d2)

    def _compare_editable(self, r_attrs, c_attrs):
        """Compare editable attributes omitting the check of generated values

        :param r_attrs: attributes from release
        :param c_attrs: attributes from cluster
        """
        if isinstance(r_attrs, dict) and isinstance(c_attrs, dict):
            for s_field, s_value in six.iteritems(r_attrs):
                if s_field not in c_attrs:
                    self.fail("'{0}' not found in '{1}'".format(s_field,
                                                                c_attrs))
                self._compare_editable(s_value, c_attrs[s_field])
        elif isinstance(c_attrs, six.string_types) and \
                isinstance(r_attrs, dict):
            self.assertIn("generator", r_attrs)
        else:
            self.assertEqual(c_attrs, r_attrs)

    def test_compare_editable(self):
        r_attrs = {
            'section1': {
                'value': 'string1'
            },
            'section2': {
                'subsection1': {
                    'value': 'string2'
                }
            }
        }
        c_attrs = {
            'section1': {
                'value': 'string1'
            },
            'section2': {
                'subsection1': {
                    'value': 'string2'
                }
            }
        }
        self._compare_editable(r_attrs, c_attrs)

        r_attrs['section1']['value'] = {
            'generator': 'generator1'
        }
        self._compare_editable(r_attrs, c_attrs)

        r_attrs['section2']['subsection1']['value'] = {
            'generator': 'generator2'
        }
        self._compare_editable(r_attrs, c_attrs)

        r_attrs['section1']['value'] = 'zzzzzzz'
        self.assertRaises(
            AssertionError, self._compare_editable, r_attrs, c_attrs)

    def test_editable_attributes_generators(self):
        self.env.create_cluster(api=True)
        cluster = self.env.clusters[0]
        editable = objects.Cluster.get_attributes(cluster).editable
        self.assertEqual(
            editable["external_dns"]["dns_list"]["value"],
            settings.DNS_UPSTREAM
        )
        self.assertEqual(
            editable["external_ntp"]["ntp_list"]["value"],
            settings.NTP_UPSTREAM
        )
