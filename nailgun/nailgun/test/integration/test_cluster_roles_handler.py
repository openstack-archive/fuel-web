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

from nailgun.test import base


class TestClusterRolesHandler(base.BaseTestCase):

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
            self.assertEquals(resp.status_code, 405)
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

        self.assertEquals(role['name'], self.role_name)
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

        self.assertEquals(resp.status_code, 404)
        self.assertIn("Role is not found for the cluster",
                      resp.json_body['message'])

    def test_not_allowed_methods_for_single_role(self):
        url = base.reverse(
            'ClusterRolesHandler',
            {'cluster_id': self.cluster.id, 'role_name': self.role_name}
        )
        self._check_methods_not_allowed(url)
