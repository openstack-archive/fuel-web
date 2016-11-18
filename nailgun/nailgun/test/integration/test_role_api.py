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


import yaml

from nailgun.test import base


class BaseRoleTest(base.BaseIntegrationTest):

    ROLE = ""

    def setUp(self):
        super(BaseRoleTest, self).setUp()
        self.cluster = self.env.create()
        self.release = self.cluster.release
        self.role_data = yaml.load(self.ROLE)
        self.tag_data = {'name': 'my_tag', 'meta': {'has_primary': True}}


class TestRoleApi(BaseRoleTest):

    ROLE = """
    name: my_role
    meta:
        name: My Role
        description: Something goes here
        tags: [my_tag]
    volumes_roles_mapping:
        - id: os
          allocate_size: all
    """

    def test_get_all_release_roles(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)

        resp = self.env.get_all_roles(owner_type, owner_id)

        self.assertEqual(
            len(self.release.roles_metadata.keys()),
            len(resp.json))

        created_role = next((
            role
            for role in resp.json if role['name'] == self.role_data['name']))
        self.assertEqual(created_role, self.role_data)

    def test_get_all_cluster_roles(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)

        resp = self.env.get_all_roles(owner_type, owner_id)

        self.assertEqual(
            len(self.release.roles_metadata.keys())
            + len(self.cluster.roles_metadata.keys()),
            len(resp.json))

        created_role = next((
            role
            for role in resp.json if role['name'] == self.role_data['name']))
        self.assertEqual(created_role, self.role_data)

    def test_create_release_role(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        resp = self.env.create_role(owner_type, owner_id, self.role_data)
        self.assertEqual(resp.json['meta'], self.role_data['meta'])

    def test_create_cluster_role(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        resp = self.env.create_role(owner_type, owner_id, self.role_data)
        self.assertEqual(resp.json['meta'], self.role_data['meta'])

    def test_create_release_role_with_nonexistent_tag(self):
        owner_type, owner_id = 'releases', self.release.id
        resp = self.env.create_role(owner_type, owner_id, self.role_data,
                                    expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertIn('contains non-existent tag', resp.body)

    def test_create_cluster_role_with_nonexistent_tag(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        resp = self.env.create_role(owner_type, owner_id, self.role_data,
                                    expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertIn('contains non-existent tag', resp.body)

    def test_update_release_role(self):
        changed_name = 'Another name'
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        resp = self.env.create_role(owner_type, owner_id, self.role_data)

        data = resp.json
        data['meta']['name'] = changed_name

        resp = self.env.update_role(owner_type, owner_id, data['name'], data)
        self.assertEqual(resp.json['meta']['name'], changed_name)

    def test_update_cluster_role(self):
        changed_name = 'Another name'
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        resp = self.env.create_role(owner_type, owner_id, self.role_data)

        data = resp.json
        data['meta']['name'] = changed_name

        resp = self.env.update_role(owner_type, owner_id, data['name'], data)
        self.assertEqual(resp.json['meta']['name'], changed_name)

    def test_update_release_role_with_nonexistent_tag(self):
        tag = 'nonexistent_tag'
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        resp = self.env.create_role(owner_type, owner_id, self.role_data)

        data = resp.json
        data['meta']['tags'] = [tag]

        resp = self.env.update_role(owner_type, owner_id, data['name'], data,
                                    expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertIn('contains non-existent tag', resp.body)

    def test_update_cluster_role_with_nonexistent_tag(self):
        tag = 'nonexistent_tag'
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        resp = self.env.create_role(owner_type, owner_id, self.role_data)

        data = resp.json
        data['meta']['tags'] = [tag]

        resp = self.env.update_role(owner_type, owner_id, data['name'], data,
                                    expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertIn('contains non-existent tag', resp.body)

    def test_create_release_role_wo_volumes(self):
        owner_type, owner_id = 'releases', self.release.id
        self.role_data['volumes_roles_mapping'] = []
        resp = self.env.create_role(
            owner_type, owner_id, self.role_data, expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_create_cluster_role_wo_volumes(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.role_data['volumes_roles_mapping'] = []
        resp = self.env.create_role(
            owner_type, owner_id, self.role_data, expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_create_release_role_w_invalid_volumes_allocate_size(self):
        owner_type, owner_id = 'releases', self.release.id
        self.role_data['volumes_roles_mapping'][0]['allocate_size'] = \
            'some_string'
        resp = self.env.create_role(
            owner_type, owner_id, self.role_data, expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertIn('Failed validating', resp.body)
        self.assertIn('volumes_roles_mapping', resp.body)

    def test_create_cluster_role_w_invalid_volumes_allocate_size(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.role_data['volumes_roles_mapping'][0]['allocate_size'] = \
            'some_string'
        resp = self.env.create_role(
            owner_type, owner_id, self.role_data, expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertIn('Failed validating', resp.body)
        self.assertIn('volumes_roles_mapping', resp.body)

    def test_create_release_role_w_invalid_id(self):
        owner_type, owner_id = 'releases', self.release.id
        self.role_data['volumes_roles_mapping'][0]['id'] = 'invalid_id'
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        resp = self.env.create_role(
            owner_type, owner_id, self.role_data, expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertIn('Wrong data in volumes_roles_mapping', resp.body)

    def test_create_cluster_role_w_invalid_id(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.role_data['volumes_roles_mapping'][0]['id'] = 'invalid_id'
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        resp = self.env.create_role(
            owner_type, owner_id, self.role_data, expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertIn('Wrong data in volumes_roles_mapping', resp.body)

    def test_update_release_role_w_invalid_volumes_id(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        self.role_data['volumes_roles_mapping'][0]['id'] = 'some_string'
        resp = self.env.update_role(owner_type,
                                    owner_id,
                                    self.role_data['name'],
                                    self.role_data,
                                    expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertIn('Wrong data in volumes_roles_mapping', resp.body)

    def test_update_cluster_role_w_invalid_volumes_id(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        self.role_data['volumes_roles_mapping'][0]['id'] = 'some_string'
        resp = self.env.update_role(owner_type,
                                    owner_id,
                                    self.role_data['name'],
                                    self.role_data,
                                    expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertIn('Wrong data in volumes_roles_mapping', resp.body)

    def test_update_release_role_not_present(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        role_name = 'blah_role'
        resp = self.env.update_role(owner_type,
                                    owner_id,
                                    role_name,
                                    self.role_data,
                                    expect_errors=True)
        self.assertEqual(404, resp.status_code)
        self.assertIn('is not found for the release', resp.body)

    def test_update_cluster_role_not_present(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        role_name = 'blah_role'
        resp = self.env.update_role(owner_type,
                                    owner_id,
                                    role_name,
                                    self.role_data,
                                    expect_errors=True)
        self.assertEqual(404, resp.status_code)
        self.assertIn('is not found for the cluster', resp.body)

    def test_delete_release_role(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        delete_resp = self.env.delete_role(
            owner_type, owner_id, self.role_data['name'])

        self.assertEqual(delete_resp.status_code, 204)

    def test_delete_cluster_role(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        delete_resp = self.env.delete_role(
            owner_type, owner_id, self.role_data['name'])

        self.assertEqual(delete_resp.status_code, 204)

    def test_delete_release_role_not_present(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        role_name = 'blah_role'
        delete_resp = self.env.delete_role(
            owner_type, owner_id, role_name, expect_errors=True)
        self.assertEqual(delete_resp.status_code, 404)
        self.assertIn('is not found for the release', delete_resp.body)

    def test_delete_cluster_role_not_present(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        role_name = 'blah_role'
        delete_resp = self.env.delete_role(
            owner_type, owner_id, role_name, expect_errors=True)
        self.assertEqual(delete_resp.status_code, 404)
        self.assertIn('is not found for the cluster', delete_resp.body)

    def test_delete_assigned_release_role(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        role = self.env.create_role(owner_type, owner_id, self.role_data).json
        self.env.create(
            nodes_kwargs=[
                {'roles': [role['name']], 'pending_addition': True},
            ],
            cluster_kwargs={'release_id': self.release.id},
        )

        delete_resp = self.env.delete_role(
            owner_type, owner_id, role['name'], expect_errors=True)
        self.assertEqual(delete_resp.status_code, 400)

    def test_delete_assigned_cluster_role(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        role = self.env.create_role(owner_type, owner_id, self.role_data).json
        self.env.create_node(api=False, cluster_id=self.cluster.id,
                             pending_addition=True,
                             roles=[role['name']])
        delete_resp = self.env.delete_role(
            owner_type, owner_id, role['name'], expect_errors=True)
        self.assertEqual(delete_resp.status_code, 400)

    def test_delete_release_role_when_assigned_another_role(self):
        # There was bug with such validation
        # https://bugs.launchpad.net/fuel/+bug/1488091
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        role = self.env.create_role(owner_type, owner_id, self.role_data).json
        self.env.create(
            nodes_kwargs=[
                {'roles': ['compute'], 'pending_addition': True},
            ],
            cluster_kwargs={'release_id': self.release.id},
        )

        delete_resp = self.env.delete_role(owner_type, owner_id, role['name'])
        self.assertEqual(delete_resp.status_code, 204)

    def test_delete_cluster_role_when_assigned_another_role(self):
        # There was bug with such validation
        # https://bugs.launchpad.net/fuel/+bug/1488091
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        role = self.env.create_role(owner_type, owner_id, self.role_data).json
        self.env.create(
            nodes_kwargs=[
                {'roles': ['compute'], 'pending_addition': True},
            ],
            cluster_kwargs={'release_id': self.release.id},
        )

        delete_resp = self.env.delete_role(owner_type, owner_id, role['name'])
        self.assertEqual(delete_resp.status_code, 204)

    def test_delete_pending_assigned_release_role(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        role = self.env.create_role(owner_type, owner_id, self.role_data).json
        self.env.create(
            nodes_kwargs=[
                {'pending_roles': [role['name']], 'pending_addition': True},
            ],
            cluster_kwargs={'release_id': self.release.id},
        )

        delete_resp = self.env.delete_role(
            owner_type, owner_id, role['name'], expect_errors=True)
        self.assertEqual(delete_resp.status_code, 400)

    def test_delete_pending_assigned_cluster_role(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        role = self.env.create_role(owner_type, owner_id, self.role_data).json
        self.env.create_node(api=False, cluster_id=self.cluster.id,
                             pending_addition=True,
                             pending_roles=[role['name']])

        delete_resp = self.env.delete_role(
            owner_type, owner_id, role['name'], expect_errors=True)
        self.assertEqual(delete_resp.status_code, 400)

    def test_get_release_role(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        role = self.env.get_role(owner_type, owner_id, self.role_data['name'])

        self.assertEqual(role.status_code, 200)
        self.assertEqual(role.json['name'], self.role_data['name'])

    def test_get_cluster_role(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        role = self.env.get_role(owner_type, owner_id, self.role_data['name'])

        self.assertEqual(role.status_code, 200)
        self.assertEqual(role.json['name'], self.role_data['name'])

    def test_get_release_role_not_present(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        role_name = 'blah_role'
        resp = self.env.get_role(
            owner_type, owner_id, role_name, expect_errors=True)
        self.assertEqual(resp.status_code, 404)
        self.assertIn('is not found for the release', resp.body)

    def test_get_cluster_role_not_present(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        self.env.create_role(owner_type, owner_id, self.role_data)
        role_name = 'blah_role'
        resp = self.env.get_role(
            owner_type, owner_id, role_name, expect_errors=True)
        self.assertEqual(resp.status_code, 404)
        self.assertIn('is not found for the cluster', resp.body)

    def test_create_release_role_with_special_symbols(self):
        owner_type, owner_id = 'releases', self.release.id
        self.role_data['name'] = '@#$%^&*()'
        resp = self.env.create_role(
            owner_type, owner_id, self.role_data, expect_errors=True)

        self.assertEqual(resp.status_code, 400)

    def test_create_cluster_role_with_special_symbols(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.role_data['name'] = '@#$%^&*()'
        resp = self.env.create_role(
            owner_type, owner_id, self.role_data, expect_errors=True)

        self.assertEqual(resp.status_code, 400)


class TestFullDataRole(BaseRoleTest):

    ROLE = """
---
name: new_controller
meta:
    name: "Controller"
    description: "The controller initiates orchestration activities."
    conflicts:
      - compute
    update_required:
      - compute
      - cinder
    has_primary: true
    limits:
      min: 1
      overrides:
        - condition: "cluster:mode == 'multinode'"
          max: 1
          message: "Multi-node environment can not have more."
    restrictions:
        - "cluster:mode == 'multinode'"
        - multinode: true
        - condition: "cluster:mode == 'multinode'"
          action: hide
          message: "Multi-node environment can not have more."
    tags:
      - my_tag
volumes_roles_mapping:
    - id: os
      allocate_size: all
"""

    def test_create_release_role(self):
        owner_type, owner_id = 'releases', self.release.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        resp = self.env.create_role(owner_type, owner_id, self.role_data)
        self.assertEqual(resp.json['meta'], self.role_data['meta'])

    def test_create_cluster_role(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_tag(owner_type, owner_id, self.tag_data)
        resp = self.env.create_role(owner_type, owner_id, self.role_data)
        self.assertEqual(resp.json['meta'], self.role_data['meta'])
