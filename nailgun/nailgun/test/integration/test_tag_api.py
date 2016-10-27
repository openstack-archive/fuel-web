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

from nailgun import consts
from nailgun.test import base


class TestTagApi(base.BaseIntegrationTest):

    owner_url = "/api/{}/{}/tags/"
    owner_map = {
        consts.TAG_OWNER_TYPES.release: 'releases',
        consts.TAG_OWNER_TYPES.cluster: 'clusters',
        consts.TAG_OWNER_TYPES.plugin: 'plugins'
    }

    def setUp(self):
        super(TestTagApi, self).setUp()
        self.release = self.env.create_release()
        self.cluster = self.env.create_cluster(release_id=self.release.id)
        self.plugin = self.env.create_plugin(cluster=self.cluster)
        self.node = self.env.create_node(api=False,
                                         cluster_id=self.cluster.id,
                                         pending_roles=['controller'],
                                         pending_addition=True)
        self.tag_data = {'tag': 'my_tag', 'has_primary': False}

    def _get_all_tags(self, owner, owner_id):
        return self.app.get(self.owner_url.format(self.owner_map[owner],
                                                  owner_id),
                            headers=self.default_headers)

    def _test_get_tags(self, owner, owner_id):
        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)
        resp = self._get_all_tags(owner, owner_id)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue([t for t in resp.json if t['id'] == n_tag['id']])

    def test_get_release_tags(self):
        self._test_get_tags(consts.TAG_OWNER_TYPES.release, self.release.id)

    def test_get_cluster_tags(self):
        self._test_get_tags(consts.TAG_OWNER_TYPES.cluster, self.cluster.id)

    def test_get_plugins_tags(self):
        self._test_get_tags(consts.TAG_OWNER_TYPES.plugin, self.plugin.id)

    def test_create_get_tag(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data)
        self.assertEqual(resp.status_code, 201)

        resp = self.env.get_tag(resp.json['id'])
        self.assertEqual(resp.status_code, 200)
        self.assertDictContainsSubset(self.tag_data, resp.json)

    def test_failed_create_tag_with_same_name_in_cluster_namespace(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data)
        self.assertEqual(resp.status_code, 201)

        owner, owner_id = consts.TAG_OWNER_TYPES.release, self.release.id
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data,
                                   expect_errors=True)

        self.assertEqual(resp.status_code, 409)
        self.assertIn("is already present", resp.body)

        owner, owner_id = consts.TAG_OWNER_TYPES.plugin, self.plugin.id
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data,
                                   expect_errors=True)

        self.assertEqual(resp.status_code, 409)
        self.assertIn("is already present", resp.body)

    def test_failed_create_tag_with_same_name_in_release_namespace(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.release, self.release.id
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data)
        self.assertEqual(resp.status_code, 201)

        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data,
                                   expect_errors=True)
        self.assertEqual(resp.status_code, 409)
        self.assertIn("is already present", resp.body)

        owner, owner_id = consts.TAG_OWNER_TYPES.plugin, self.plugin.id
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data,
                                   expect_errors=True)

        self.assertEqual(resp.status_code, 409)
        self.assertIn("is already present", resp.body)

    def test_failed_create_tag_with_same_name_in_plugin_namespace(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.plugin, self.plugin.id
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data)
        self.assertEqual(resp.status_code, 201)

        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data,
                                   expect_errors=True)

        self.assertEqual(resp.status_code, 409)
        self.assertIn("is already present", resp.body)

        owner, owner_id = consts.TAG_OWNER_TYPES.release, self.release.id
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data,
                                   expect_errors=True)

        self.assertEqual(resp.status_code, 409)
        self.assertIn("is already present", resp.body)

    def test_update_tag(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id

        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)
        n_tag.update({'tag': 'other_tag', 'has_primary': True})
        resp = self.env.update_tag(n_tag['id'], n_tag)

        self.assertEqual(resp.status_code, 200)
        self.assertDictEqual(resp.json, n_tag)

    def test_failed_update_read_only_tag(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        self.tag_data.update({'read_only': True})
        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)
        n_tag.update({'tag': 'other_tag', 'has_primary': True})
        resp = self.env.update_tag(n_tag['id'], n_tag, expect_errors=True)

        self.assertEqual(resp.status_code, 400)

    def test_failed_update_tag_name_to_existent(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id

        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)
        n_tag.update({'tag': 'controller', 'has_primary': True})
        resp = self.env.update_tag(n_tag['id'], n_tag, expect_errors=True)

        self.assertEqual(resp.status_code, 409)
        self.assertIn("Tag can not be renamed", resp.body)

    def test_delete_tag(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        n_tag = self.env.create_tag(self.owner_map[owner], owner_id,
                                    self.tag_data)
        resp = self.env.delete_tag(n_tag.json['id'])

        self.assertEqual(resp.status_code, 204)

    def test_failed_delete_read_only_tag(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        self.tag_data.update({'read_only': True})
        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)
        resp = self.env.delete_tag(n_tag['id'], expect_errors=True)

        self.assertEqual(resp.status_code, 400)

    def test_failed_delete_assigned_tag(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)

        resp = self.env.assign_tag(self.node.id, [n_tag['id']])
        self.assertEqual(resp.status_code, 200)

        resp = self.env.delete_tag(n_tag['id'], expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("is assigned to node", resp.body)

    def test_assign_unassign_tag(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)

        resp = self.env.assign_tag(self.node.id, [n_tag['id']])
        self.assertEqual(resp.status_code, 200)
        self.assertIn(n_tag['tag'], [t.tag.tag for t in self.node.tags])

        resp = self.env.unassign_tag(self.node.id, [n_tag['id']])
        self.assertEqual(resp.status_code, 204)
        self.assertNotIn(n_tag['tag'], [t.tag.tag for t in self.node.tags])

    def test_failed_assign_tag_twice(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)

        resp = self.env.assign_tag(self.node.id, [n_tag['id']])
        self.assertEqual(resp.status_code, 200)
        self.assertIn(n_tag['tag'], [t.tag.tag for t in self.node.tags])

        resp = self.env.assign_tag(self.node.id, [n_tag['id']],
                                   expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("are already assigned to", resp.body)

    def test_failed_unassign_not_assigned_tag(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)

        resp = self.env.unassign_tag(self.node.id, [n_tag['id']],
                                     expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("are not assigned to", resp.body)

    def test_failed_assign_tag_to_non_cluster_node(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)
        node = self.env.create_node(api=False)
        resp = self.env.assign_tag(node.id, [n_tag['id']],
                                   expect_errors=True)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("is not in a cluster", resp.body)

    def test_failed_create_tag_for_non_existent_cluster(self):
        cluster_ids = [c.id for c in self.env.clusters]
        owner_id = next(x for x in xrange(1, 1000) if x not in cluster_ids)
        owner = consts.TAG_OWNER_TYPES.cluster
        resp = self.env.create_tag(owner, owner_id, self.tag_data,
                                   api=True, expect_errors=True)

        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.body)

    def test_failed_create_tag_with_incorrect_data(self):
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, self.cluster.id
        self.tag_data['has_primary'] = 'abc'
        resp = self.env.create_tag(self.owner_map[owner],
                                   owner_id,
                                   self.tag_data,
                                   api=True,
                                   expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("is not of type", resp.body)

    def test_failed_assign_unassign_tag_by_name(self):
        resp = self.env.assign_tag(self.node.id,
                                   ['my_tag'],
                                   expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Comma-separated numbers list expected",
                      resp.body)

        resp = self.env.unassign_tag(self.node.id,
                                     ['my_tag'],
                                     expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Comma-separated numbers list expected",
                      resp.body)

    def test_failed_assign_tag_from_wrong_namespace_cluster(self):
        other_cluster = self.env.create_cluster(release_id=self.release.id)
        owner, owner_id = consts.TAG_OWNER_TYPES.cluster, other_cluster.id
        n_tag = self.env.create_tag(owner, owner_id, self.tag_data, api=False)

        resp = self.env.assign_tag(self.node.id, [n_tag['id']],
                                   expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("are not present in node", resp.body)
