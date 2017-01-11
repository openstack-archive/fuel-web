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

from nailgun import objects
from nailgun import plugins
from nailgun.test import base


class TestClusterRolesHandler(base.BaseTestCase):

    # TODO(apopovych): use test data from base test file
    ROLES = yaml.safe_load("""
        test_role:
          name: "Some plugin role"
          description: "Some description"
          conflicts:
            - some_not_compatible_role
          limits:
            min: 1
          restrictions:
            - condition: "some logic condition"
              message: "Some message for restriction warning"
    """)

    ROLE = yaml.safe_load("""
        name: my_role
        meta:
            name: My Role
            description: Something goes here
            tags: []
        volumes_roles_mapping:
            - id: os
              allocate_size: all
    """)

    VOLUMES = yaml.safe_load("""
        volumes_roles_mapping:
          test_role:
            - {allocate_size: "min", id: "os"}
            - {allocate_size: "all", id: "image"}

    """)

    def setUp(self):
        super(TestClusterRolesHandler, self).setUp()

        self.cluster = self.env.create_cluster(api=False)
        self.expected_roles_data = self.cluster.release.roles_metadata
        self.expected_volumes_data = \
            self.cluster.release.volumes_metadata['volumes_roles_mapping']
        self.role_data = self.ROLE

    def test_get_all_roles(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        roles = self.env.get_all_roles(owner_type, owner_id).json

        self.assertItemsEqual(
            [role['name'] for role in roles],
            self.expected_roles_data.keys()
        )

        for role in roles:
            self.assertDictEqual(
                role['meta'],
                self.expected_roles_data[role['name']]
            )
            self.assertItemsEqual(
                role['volumes_roles_mapping'],
                self.expected_volumes_data[role['name']]
            )

    def test_create_role(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        resp = self.env.create_role(owner_type, owner_id, self.ROLE)
        self.assertEqual(resp.json['meta'], self.role_data['meta'])

    def test_update_role(self):
        changed_name = 'Another name'
        owner_type, owner_id = 'clusters', self.cluster.id

        resp = self.env.create_role(owner_type, owner_id, self.role_data)

        data = resp.json
        data['meta']['name'] = changed_name

        resp = self.env.update_role(owner_type, owner_id, data['name'], data)
        self.assertEqual(resp.json['meta']['name'], changed_name)

    def test_get_role(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_role(owner_type, owner_id, self.role_data)
        role = self.env.get_role(owner_type, owner_id, self.role_data['name'])

        self.assertEqual(role.status_code, 200)
        self.assertEqual(role.json['name'], self.role_data['name'])

    def test_delete_cluster_role(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self.env.create_role(owner_type, owner_id, self.role_data)
        delete_resp = self.env.delete_role(
            owner_type, owner_id, self.role_data['name'])

        self.assertEqual(delete_resp.status_code, 204)

    def test_error_role_not_present(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        role_name = 'blah_role'
        resp = self.env.get_role(
            owner_type, owner_id, role_name, expect_errors=True)

        self.assertEqual(resp.status_code, 404)
        self.assertIn("is not found for the cluster",
                      resp.json_body['message'])

    def _create_plugin(self):
        plugin_data = self.env.get_default_plugin_metadata()
        plugin_data['roles_metadata'] = self.ROLES
        plugin_data['volumes_metadata'] = self.VOLUMES
        plugin = objects.Plugin.create(plugin_data)
        self.cluster.plugins.append(plugin)
        objects.ClusterPlugin.set_attributes(self.cluster.id,
                                             plugin.id,
                                             enabled=True)
        self.db.flush()
        return plugins.wrap_plugin(plugin)

    def test_all_roles_w_plugin(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        self._create_plugin()

        roles = self.env.get_all_roles(owner_type, owner_id).json
        self.assertItemsEqual(
            [role['name'] for role in roles],
            set(self.expected_roles_data) | set(self.ROLES),
        )

    def test_plugin_role_in_clusters_roles(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        role_name = self.ROLES.keys()[0]
        plugin_adapter = self._create_plugin()

        roles = self.env.get_all_roles(owner_type, owner_id).json
        role = [r for r in roles if r['name'] == role_name][0]
        self.assertDictEqual(
            role['meta'],
            plugin_adapter.normalized_roles_metadata[role_name]
        )
        self.assertItemsEqual(
            role['volumes_roles_mapping'],
            plugin_adapter.volumes_metadata[
                'volumes_roles_mapping'][role_name]
        )

    def test_cluster_role_overriding_release_role(self):
        owner_type, owner_id = 'releases', self.cluster.release.id
        self.env.create_role(owner_type, owner_id, self.role_data)

        owner_type, owner_id = 'clusters', self.cluster.id
        data = self.env.get_all_roles(owner_type, owner_id).json
        role_name = self.role_data['name']
        role_data = [r for r in data if r['name'] == role_name][0]
        self.assertItemsEqual(role_data['volumes_roles_mapping'],
                              self.role_data['volumes_roles_mapping'])

        self.role_data['volumes_roles_mapping'] = [
            {'allocate_size': 'min', 'id': 'os'},
            {'allocate_size': 'min', 'id': 'logs'}]
        self.env.create_role(owner_type, owner_id, self.role_data)
        data = self.env.get_all_roles(owner_type, owner_id).json
        role_data = [r for r in data if r['name'] == role_name][0]
        self.assertItemsEqual(role_data['volumes_roles_mapping'],
                              self.role_data['volumes_roles_mapping'])

    def test_cluster_not_overriding_plugin_role(self):
        owner_type, owner_id = 'clusters', self.cluster.id
        role_name = self.ROLES.keys()[0]
        self.role_data['name'] = role_name

        self.env.create_role(owner_type, owner_id, self.role_data)
        data = self.env.get_all_roles(owner_type, owner_id).json
        role_data = [r for r in data if r['name'] == role_name][0]
        self.assertItemsEqual(role_data['volumes_roles_mapping'],
                              self.role_data['volumes_roles_mapping'])

        plugin_adapter = self._create_plugin()
        data = self.env.get_all_roles(owner_type, owner_id).json
        role_data = [r for r in data if r['name'] == role_name][0]
        self.assertItemsEqual(
            role_data['volumes_roles_mapping'],
            plugin_adapter.volumes_metadata[
                'volumes_roles_mapping'][role_name]
        )
