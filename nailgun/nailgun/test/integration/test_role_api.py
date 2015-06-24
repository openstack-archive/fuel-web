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
        self.release = self.env.create_release()
        self.role_data = yaml.load(self.ROLE)


class TestRoleApi(BaseRoleTest):

    ROLE = """
    name: my_role
    meta:
        name: My Role
        description: Something goes here
    volumes_roles_mapping:
        - id: os
          allocate_size: all
    """

    def test_get_all_roles(self):
        self.env.create_role(self.release.id, self.role_data)

        resp = self.app.get(
            base.reverse(
                'RoleCollectionHandler',
                {'release_id': self.release.id}),
            headers=self.default_headers,
        )

        self.assertEqual(
            len(self.release.roles_metadata.keys()),
            len(resp.json))

        keys = self.release.roles_metadata.keys()
        created_role = next((
            role for role in resp.json if role['name'] == 'my_role'))
        self.assertEqual(created_role, self.role_data)

    def test_create_role(self):
        resp = self.env.create_role(self.release.id, self.role_data)
        self.assertEqual(resp.json['meta'], self.role_data['meta'])

    def test_update_role(self):
        changed_name = 'Another name'

        resp = self.env.create_role(self.release.id, self.role_data)

        data = resp.json
        data['meta']['name'] = changed_name

        resp = self.env.update_role(self.release.id, data['name'], data)
        self.assertEqual(resp.json['meta']['name'], changed_name)

    def test_create_role_wo_volumes(self):
        self.role_data['volumes_roles_mapping'] = []
        resp = self.env.create_role(
            self.release.id, self.role_data, expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_delete_role(self):

        self.env.create_role(self.release.id, self.role_data)
        delete_resp = self.env.delete_role(
            self.release.id, self.role_data['name'])

        self.assertEqual(delete_resp.status_code, 204)

    def test_delete_assigned_role(self):
        role = self.env.create_role(self.release.id, self.role_data).json
        self.env.create(
            nodes_kwargs=[
                {'roles': [role['name']], 'pending_addition': True},
            ],
            cluster_kwargs={'release_id': self.release.id},
        )

        delete_resp = self.env.delete_role(
            self.release.id, role['name'], expect_errors=True)
        self.assertEqual(delete_resp.status_code, 400)

    def test_delete_pending_assigned_role(self):
        role = self.env.create_role(self.release.id, self.role_data).json
        self.env.create(
            nodes_kwargs=[
                {'pending_roles': [role['name']], 'pending_addition': True},
            ],
            cluster_kwargs={'release_id': self.release.id},
        )

        delete_resp = self.env.delete_role(
            self.release.id, role['name'], expect_errors=True)
        self.assertEqual(delete_resp.status_code, 400)

    def test_get_role(self):
        self.env.create_role(self.release.id, self.role_data)
        role = self.env.get_role(self.release.id, self.role_data['name'])

        self.assertEqual(role.status_code, 200)
        self.assertEqual(role.json['name'], self.role_data['name'])

    def test_create_role_with_numbers(self):
        self.role_data['name'] = '1234'
        resp = self.env.create_role(
            self.release.id, self.role_data, expect_errors=True)

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
volumes_roles_mapping:
    - id: os
      allocate_size: all
"""

    def test_create_role(self):
        resp = self.env.create_role(self.release.id, self.role_data)
        self.assertEqual(resp.json['meta'], self.role_data['meta'])
