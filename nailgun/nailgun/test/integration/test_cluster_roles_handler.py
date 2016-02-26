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

from nailgun import objects
from nailgun.plugins import adapters
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

    VOLUMES = yaml.safe_load("""
        volumes_roles_mapping:
          test_role:
            - {allocate_size: "min", id: "os"}
            - {allocate_size: "all", id: "image"}

    """)

    def setUp(self):
        super(TestClusterRolesHandler, self).setUp()

        self.env.create_cluster(api=False)
        self.cluster = self.env.clusters[0]
        self.expected_roles_data = self.cluster.release.roles_metadata
        self.expected_volumes_data = \
            self.cluster.release.volumes_metadata['volumes_roles_mapping']
        self.role_name = 'compute'

    def _check_methods_not_allowed(self, url):
        req_kwargs = {
            'url': url,
            'expect_errors': True
        }
        not_allowed_methods = ('post', 'put', 'delete')

        for method in not_allowed_methods:
            resp = getattr(self.app, method)(**req_kwargs)
            self.assertEqual(resp.status_code, 405)
            self.assertIn("Method Not Allowed", resp.status)

    def test_get_all_roles(self):
        roles = self.app.get(
            url=base.reverse(
                'ClusterRolesCollectionHandler',
                {'cluster_id': self.cluster.id}
            ),
            headers=self.default_headers
        ).json

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

    def test_not_allowed_http_methods(self):
        url = base.reverse(
            'ClusterRolesCollectionHandler',
            {'cluster_id': self.cluster.id}
        )
        self._check_methods_not_allowed(url)

    def test_get_particular_role_for_cluster(self):
        role = self.app.get(
            url=base.reverse(
                'ClusterRolesHandler',
                {'cluster_id': self.cluster.id, 'role_name': self.role_name}
            )
        ).json

        self.assertEqual(role['name'], self.role_name)
        self.assertDictEqual(
            role['meta'],
            self.expected_roles_data[role['name']]
        )
        self.assertItemsEqual(
            role['volumes_roles_mapping'],
            self.expected_volumes_data[role['name']]
        )

    def test_error_role_not_present(self):
        role_name = 'blah_role'
        resp = self.app.get(
            url=base.reverse(
                'ClusterRolesHandler',
                {'cluster_id': self.cluster.id, 'role_name': role_name}
            ),
            expect_errors=True
        )

        self.assertEqual(resp.status_code, 404)
        self.assertIn("Role is not found for the cluster",
                      resp.json_body['message'])

    def test_not_allowed_methods_for_single_role(self):
        url = base.reverse(
            'ClusterRolesHandler',
            {'cluster_id': self.cluster.id, 'role_name': self.role_name}
        )
        self._check_methods_not_allowed(url)

    def test_all_roles_w_plugin(self):
        plugin_data = self.env.get_default_plugin_metadata()
        plugin_data['roles_metadata'] = self.ROLES
        plugin = objects.Plugin.create(plugin_data)
        self.cluster.plugins.append(plugin)
        objects.ClusterPlugin.set_attributes(self.cluster.id,
                                             plugin.id,
                                             enabled=True)
        self.db.flush()

        roles = self.app.get(
            url=base.reverse(
                'ClusterRolesCollectionHandler',
                {'cluster_id': self.cluster.id}
            ),
            headers=self.default_headers
        ).json

        self.assertItemsEqual(
            [role['name'] for role in roles],
            set(self.expected_roles_data) | set(self.ROLES),
        )

    def test_get_particular_role_for_cluster_w_plugin(self):
        plugin_data = self.env.get_default_plugin_metadata()
        plugin_data['roles_metadata'] = self.ROLES
        plugin_data['volumes_metadata'] = self.VOLUMES
        plugin = objects.Plugin.create(plugin_data)
        self.cluster.plugins.append(plugin)
        objects.ClusterPlugin.set_attributes(self.cluster.id,
                                             plugin.id,
                                             enabled=True)
        self.db.flush()
        plugin_adapter = adapters.wrap_plugin(plugin)

        role = self.app.get(
            url=base.reverse(
                'ClusterRolesHandler',
                {'cluster_id': self.cluster.id, 'role_name': 'test_role'}
            )
        ).json

        self.assertEqual(role['name'], 'test_role')
        self.assertDictEqual(
            role['meta'],
            plugin_adapter.normalized_roles_metadata['test_role']
        )
        self.assertItemsEqual(
            role['volumes_roles_mapping'],
            plugin_adapter.volumes_metadata[
                'volumes_roles_mapping']['test_role']
        )
