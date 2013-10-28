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

from nailgun.api.models import Attributes
from nailgun.api.models import Cluster
from nailgun.api.models import Release
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestAttributes(BaseIntegrationTest):

    def test_attributes_creation(self):
        cluster = self.env.create_cluster(api=True)
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        release = self.db.query(Release).get(
            cluster['release']['id']
        )
        self.assertEquals(200, resp.status)
        self.assertEquals(
            json.loads(resp.body)['editable'],
            release.attributes_metadata['editable']
        )
        attrs = self.db.query(Attributes).filter(
            Attributes.cluster_id == cluster['id']
        ).first()
        self._compare(
            release.attributes_metadata['generated'],
            attrs.generated
        )

    def test_500_if_no_attributes(self):
        cluster = self.env.create_cluster(api=False)
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
        self.assertEquals(500, resp.status)

    def test_attributes_update(self):
        cluster_id = self.env.create_cluster(api=True)['id']
        resp = self.app.get(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster_id}),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status)
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
        self.assertEquals(200, resp.status)
        attrs = self.db.query(Attributes).filter(
            Attributes.cluster_id == cluster_id
        ).first()
        self.assertEquals("bar", attrs.editable["foo"])
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
        self.assertEquals(400, resp.status)
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
        self.assertEquals(400, resp.status)

    def test_get_default_attributes(self):
        cluster = self.env.create_cluster(api=True)
        release = self.db.query(Release).get(
            cluster['release']['id']
        )
        resp = self.app.put(
            reverse(
                'ClusterAttributesDefaultsHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status)
        self.assertEquals(
            json.loads(resp.body)['editable'],
            release.attributes_metadata['editable']
        )

    def test_attributes_set_defaults(self):
        cluster = self.env.create_cluster(api=True)
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
        self.assertEquals(200, resp.status)
        attrs = self.db.query(Attributes).filter(
            Attributes.cluster_id == cluster['id']
        ).first()
        self.assertEquals("bar", attrs.editable["foo"])
        # Set attributes to defaults.
        resp = self.app.put(
            reverse(
                'ClusterAttributesDefaultsHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status)
        release = self.db.query(Release).get(
            cluster['release']['id']
        )
        self.assertEquals(
            json.loads(resp.body)['editable'],
            release.attributes_metadata['editable']
        )

    def test_attributes_merged_values(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.db.query(Cluster).get(cluster['id'])
        orig_attrs = cluster_db.attributes.merged_attrs()
        attrs = cluster_db.attributes.merged_attrs_values()

        def func(struct):
            if isinstance(struct, (dict,)) and "value" in struct:
                return struct["value"]
            return struct

        orig_attrs = Attributes.traverse(orig_attrs, func)
        if 'common' in orig_attrs:
            orig_attrs.update(orig_attrs.pop('common'))
        if 'additional_components' in orig_attrs:
            addcomps = orig_attrs['additional_components']
            for comp, enabled in addcomps.iteritems():
                orig_attrs.setdefault(comp, {}).update({
                    "enabled": enabled
                })
            orig_attrs.pop('additional_components')

        self.assertEquals(attrs, orig_attrs)

    def test_attributes_obscure(self):
        self.env.create_cluster(api=True)
        self.env.create_cluster(api=True)

        obscure = []

        def func(struct):
            if (isinstance(struct, (dict,)) and
                struct.get('obscure', False) and
                    'value' in struct):
                    obscure.append(struct['value'])
            return struct

        for cluster in self.db.query(Cluster):
            attrs = cluster.attributes.merged_attrs()
            Attributes.traverse(attrs, func)

        self.assertEquals(sorted(obscure), sorted(Attributes.obscure()))

    def test_attributes_traverse(self):
        orig = {
            "key0": {
                "key00": {
                    "key000": "value001",
                    "key001": "value001",
                    "subs": True,
                    "obscure": True,
                    "value": "secret00"
                }
            },
            "key1": {
                "key10": {
                    "key100": {
                        "key1000": "value1000",
                        "key1001": "value1001",
                        "subs": True,
                        "obscure": False,
                        "value": "secret1000"
                    },
                    "key101": "value101"
                }
            }
        }

        def func_subs(struct):
            if isinstance(struct, (dict,)) and "value" in struct:
                return struct["value"]
            return struct

        orig_subs = {
            "key0": {
                "key00": "secret00"
            },
            "key1": {
                "key10": {
                    "key100": "secret1000",
                    "key101": "value101"
                }
            }
        }
        self.assertEquals(Attributes.traverse(orig, func_subs), orig_subs)

        obscure = []

        def func_obscure(struct):
            if isinstance(struct, (dict,)) and struct.get("obscure", False):
                obscure.append(struct["value"])
            return struct
        Attributes.traverse(orig, func_obscure)
        self.assertEquals(sorted(obscure), sorted(["secret00"]))

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
