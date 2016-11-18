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

from nailgun import objects
from nailgun.test import base


class TestReleaseTagsHandler(base.BaseTestCase):

    def setUp(self):
        super(TestReleaseTagsHandler, self).setUp()
        self.cluster = self.env.create(api=False,
                                       nodes_kwargs=[
                                           {'pending_roles': ['controller']},
                                           {'pending_roles': ['controller']},
                                           {'pending_roles': ['controller']}])

        objects.Cluster.set_primary_tags(self.cluster, self.cluster.nodes)
        self.release = self.cluster.release
        self.tag_data = {'name': 'my_tag', 'meta': {'has_primary': True}}
        self.role_data = {'name': 'my_role',
                          'meta': {'name': 'My Role',
                                   'description': 'Something goes here',
                                   'tags': ['my_tag']
                                   },
                          'volumes_roles_mapping':
                              [{'id': 'os', 'allocate_size': 'all'}]}

    def test_get_all_tags(self):
        owner_type, owner_id = 'releases', self.release.id
        resp = self.env.get_all_tags(owner_type, owner_id)

        self.assertEqual(
            len(self.release.tags_metadata.keys()),
            len(resp.json))

    def test_create_tag(self):
        owner_type, owner_id = 'releases', self.release.id
        resp = self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.assertEqual(resp.json['meta'], self.tag_data['meta'])

        resp = self.env.get_all_tags(owner_type, owner_id)

        created_tag = next((
            tag
            for tag in resp.json if tag['name'] == self.tag_data['name']))
        self.assertEqual(created_tag, self.tag_data)

    def test_update_tag(self):
        has_primary = True
        owner_type, owner_id = 'releases', self.release.id

        resp = self.env.create_tag(owner_type, owner_id, self.tag_data)

        data = resp.json
        data['meta']['has_primary'] = has_primary

        resp = self.env.update_tag(owner_type, owner_id, data['name'], data)
        self.assertTrue(resp.json['meta']['has_primary'])

    def test_update_tag_not_present(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        tag_name = 'blah_tag'
        resp = self.env.update_tag(owner_type,
                                   owner_id,
                                   tag_name,
                                   self.tag_data,
                                   expect_errors=True)
        self.assertEqual(404, resp.status_code)
        self.assertIn('is not found for the release', resp.body)

    def test_delete_tag(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        cluster = self.env.create(
            cluster_kwargs={'release_id': self.release.id})
        self.env.create_role('clusters', cluster.id, self.role_data)
        self.env.create_node(api=False, cluster_id=cluster.id,
                             pending_roles=[self.role_data['name']])
        self.env.create_node(api=False, cluster_id=cluster.id,
                             pending_roles=[self.role_data['name']])
        self.env.create_node(api=False, cluster_id=cluster.id,
                             pending_roles=[self.role_data['name']])
        objects.Cluster.set_primary_tags(cluster, cluster.nodes)

        delete_resp = self.env.delete_tag(
            owner_type, owner_id, self.tag_data['name'])

        self.assertEqual(delete_resp.status_code, 204)
        self.assertNotIn(
            self.tag_data['name'],
            cluster.roles_metadata[self.role_data['name']]['tags'])
        for node in cluster.nodes:
            self.assertNotIn(self.tag_data['name'], node.primary_tags)

    def test_delete_tag_not_present(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        tag_name = 'blah_tag'
        delete_resp = self.env.delete_tag(
            owner_type, owner_id, tag_name, expect_errors=True)
        self.assertEqual(delete_resp.status_code, 404)
        self.assertIn('is not found for the release', delete_resp.body)

    def test_get_tag(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        tag = self.env.get_tag(owner_type, owner_id, self.tag_data['name'])

        self.assertEqual(tag.status_code, 200)
        self.assertEqual(tag.json['name'], self.tag_data['name'])

    def test_get_tag_not_present(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        tag_name = 'blah_tag'
        resp = self.env.get_tag(
            owner_type, owner_id, tag_name, expect_errors=True)
        self.assertEqual(resp.status_code, 404)
        self.assertIn('is not found for the release', resp.body)

    def test_create_tag_with_special_symbols(self):
        owner_type, owner_id = 'releases', self.release.id
        self.tag_data['name'] = '@#$%^&*()'
        resp = self.env.create_tag(
            owner_type, owner_id, self.tag_data, expect_errors=True)

        self.assertEqual(resp.status_code, 400)


class TestClusterTagsHandler(base.BaseTestCase):

    def setUp(self):
        super(TestClusterTagsHandler, self).setUp()
        self.cluster = self.env.create(api=False,
                                       nodes_kwargs=[
                                           {'pending_roles': ['controller']},
                                           {'pending_roles': ['controller']},
                                           {'pending_roles': ['controller']}])
        objects.Cluster.set_primary_tags(self.cluster, self.cluster.nodes)
        self.tag_data = {'name': 'my_tag', 'meta': {'has_primary': True}}
        self.release = self.cluster.release
        self.role_data = {'name': 'my_role',
                          'meta': {'name': 'My Role',
                                   'description': 'Something goes here',
                                   'tags': ['my_tag']
                                   },
                          'volumes_roles_mapping':
                              [{'id': 'os', 'allocate_size': 'all'}]}

    def test_get_all_tags(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        resp = self.env.get_all_tags(owner_type, owner_id)

        self.assertEqual(
            len(self.cluster.release.tags_metadata.keys() +
                self.cluster.tags_metadata.keys()),
            len(resp.json))

    def test_create_tag(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        resp = self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.assertEqual(resp.json['meta'], self.tag_data['meta'])

        resp = self.env.get_all_tags(owner_type, owner_id)

        created_tag = next((
            tag
            for tag in resp.json if tag['name'] == self.tag_data['name']))
        self.assertEqual(created_tag, self.tag_data)

    def test_update_tag(self):
        changed_name = 'Another name'
        owner_type, owner_id = 'clusters', self.cluster.id

        resp = self.env.create_tag(owner_type, owner_id, self.tag_data)

        data = resp.json
        data['meta']['name'] = changed_name

        resp = self.env.update_tag(owner_type, owner_id, data['name'], data)
        self.assertEqual(resp.json['meta']['name'], changed_name)

    def test_get_tag(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        tag = self.env.get_tag(owner_type, owner_id, self.tag_data['name'])

        self.assertEqual(tag.status_code, 200)
        self.assertEqual(tag.json['name'], self.tag_data['name'])

    def test_delete_tag(self):
        cluster = self.env.create(
            cluster_kwargs={'release_id': self.release.id})
        owner_type, owner_id = 'clusters', cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        self.env.create_node(api=False, cluster_id=owner_id,
                             pending_roles=[self.role_data['name']])
        self.env.create_node(api=False, cluster_id=owner_id,
                             pending_roles=[self.role_data['name']])
        self.env.create_node(api=False, cluster_id=owner_id,
                             pending_roles=[self.role_data['name']])
        objects.Cluster.set_primary_tags(cluster, cluster.nodes)
        delete_resp = self.env.delete_tag(
            owner_type, owner_id, self.tag_data['name'])
        self.assertEqual(delete_resp.status_code, 204)
        self.assertNotIn(
            self.tag_data['name'],
            cluster.roles_metadata[self.role_data['name']]['tags'])
        for node in cluster.nodes:
            self.assertNotIn(self.tag_data['name'], node.primary_tags)

    def test_error_tag_not_present(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        tag_name = 'blah_tag'
        resp = self.env.get_tag(
            owner_type, owner_id, tag_name, expect_errors=True)

        self.assertEqual(resp.status_code, 404)
        self.assertIn("is not found for the cluster",
                      resp.json_body['message'])
