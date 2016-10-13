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


import yaml

from nailgun.test import base
from nailgun.consts import TAG_OWNER_TYPES


class TestTagApi(base.BaseIntegrationTest):

    TAG = """
    tag: my_tag
    has_primary: false
    """
    owner_url = "/api/{}/{}/tags/"
    owner_map = {
        'release': 'releases',
        'cluster': 'clusters',
        'plugin': 'plugins'
    }

    def setUp(self):
        super(TestTagApi, self).setUp()
        self.node = self.env.create_node()
        self.release = self.env.create_release()
        self.cluster = self.env.create_cluster()
        self.plugin = self.env.create_plugin()
        self.tag_data = yaml.load(self.TAG)
        self.env.assign_nodes(self.cluster.id, [self.node.id])

    def _get_all_tags(self, owner, owner_id):
        return self.app.get(self.owner_url.format(self.owner_map[owner], owner_id),
                            headers=self.default_headers)

    def _test_create_get_tags(self, owner, owner_id):
        n_tag = self.env.create_tag(self.owner_map[owner], owner_id,
                                    self.tag_data).json
        all_tags = self._get_all_tags(owner, owner_id).json
        self.assertTrue([t for t in all_tags if t['id'] == n_tag['id']])

    def test_create_get_release_tags(self):
        self._test_create_get_tags(TAG_OWNER_TYPES.release, self.release.id)

    def test_create_get_cluster_tags(self):
        self._test_create_get_tags(TAG_OWNER_TYPES.cluster, self.cluster.id)

    def test_create_get_plugins_tags(self):
        self._test_create_get_tags(TAG_OWNER_TYPES.plugin, self.plugin.id)

    def test_create_get_tag(self):
        owner, owner_id = TAG_OWNER_TYPES.cluster, self.cluster.id
        n_tag = self.env.create_tag(self.owner_map[owner], owner_id, self.tag_data)
        resp = self.env.get_tag(n_tag.json['id'], n_tag)

        self.assertEqual(resp.status_code, 200)
        self.assertDictEqual(resp.json, n_tag.json)

    def test_update_tag(self):
        owner, owner_id = TAG_OWNER_TYPES.cluster, self.cluster.id
        
        n_tag = self.env.create_tag(self.owner_map[owner], owner_id,
                                    self.tag_data).json
        n_tag.update({'tag': 'other_tag', 'has_primary': True})
        resp = self.env.update_tag(n_tag['id'], n_tag)

        self.assertEqual(resp.status_code, 200)
        self.assertDictEqual(resp.json, n_tag)

    def test_delete_tag(self):
        owner, owner_id = TAG_OWNER_TYPES.cluster, self.cluster.id
        n_tag = self.env.create_tag(self.owner_map[owner], owner_id,
                                    self.tag_data)
        resp = self.env.delete_tag(n_tag.json['id'])

        self.assertEqual(resp.status_code, 204)

#    def _test_assign_tag(self):
#        owner, owner_id = TAG_OWNER_TYPES.cluster, self.cluster.id
#        n_tag = self.env.create_tag(self.owner_map[owner], owner_id,
#                                    self.tag_data).json
#        resp = self.env.assign_tag(self.node.id, [n_tag['id']])
#
#        self.assertEqual(resp.status_code, 200)
#
#    def test_assign_tag(self):
#        self._test_assign_tag()
#
#    def test_unassign_tag(self):
#        resp = self.env.create_tag(self.release.id, self.role_data)
#        self.assertEqual(resp.json['meta'], self.role_data['meta'])
