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

    def test_get_all_roles(self):
        roles = self.app.get(
            url=base.reverse(
                'ClusterRolesCollectionHandler',
                {'cluster_id': self.cluster.id}
            ),
            headers=self.default_headers
        ).json

        self.assertEquals(
            sorted([role['name'] for role in roles]),
            sorted(self.expected_roles_data.keys())
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

    def test_get_particular_role_for_cluster(self):
        role_name = 'compute'
        role = self.app.get(
            url=base.reverse(
                'ClusterRolesHandler',
                {'cluster_id': self.cluster.id, 'role_name': role_name}
            )
        ).json

        self.assertEquals(role['name'], role_name)
        self.assertDictEqual(
            role['meta'],
            self.expected_roles_data[role['name']]
        )
        self.assertItemsEqual(
            role['volumes_roles_mapping'],
            self.expected_volumes_data[role['name']]
        )
