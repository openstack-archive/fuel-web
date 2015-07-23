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

from oslo_serialization import jsonutils

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestRoles(BaseIntegrationTest):

    def test_roles_update(self):
        self.env.create_release()
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )
        test_role_name = "testrole"

        release_json = resp.json_body[0]
        old_roles = set(release_json["roles_metadata"].keys())
        release_json["roles_metadata"][test_role_name] = {}

        resp = self.app.put(
            reverse('ReleaseHandler',
                    kwargs={"obj_id": release_json["id"]}),
            jsonutils.dumps(release_json),
            headers=self.default_headers
        )
        new_roles = set(resp.json_body["roles_metadata"].keys())
        self.assertIn(test_role_name, new_roles)
        self.assertLessEqual(old_roles, new_roles)

    def test_roles_add_and_remove(self):
        self.env.create_release()
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )
        test_role_name = "testrole"

        release_json = resp.json_body[0]
        old_roles = release_json["roles_metadata"].keys()
        release_json["roles_metadata"][test_role_name] = {}
        release_json["roles_metadata"].pop(old_roles[0])
        expected_roles = list(release_json["roles_metadata"].keys())

        resp = self.app.put(
            reverse('ReleaseHandler',
                    kwargs={"obj_id": release_json["id"]}),
            jsonutils.dumps(release_json),
            headers=self.default_headers
        )
        new_roles = resp.json_body["roles_metadata"].keys()
        self.assertItemsEqual(expected_roles, new_roles)

    def test_roles_add_duplicated_through_handler(self):
        self.env.create_release()
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )

        release_json = resp.json_body[0]
        old_roles = release_json["roles_metadata"].keys()
        duplicated_role = old_roles[0]

        resp = self.env.create_role(release_json["id"], {
            "name": duplicated_role,
            "meta": {
                "name": "yep role",
                "description": ""
            },
            "volumes_roles_mapping": [{
                "id": "os",
                "allocate_size": "all",
            }],
        }, expect_errors=True)

        self.assertEqual(resp.status_code, 409)
        self.assertRegexpMatches(
            resp.json_body["message"],
            "Role with name {0} already exists for release.*".format(
                duplicated_role))

    def test_roles_delete(self):
        self.env.create_release()
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )

        release_json = resp.json_body[0]
        old_roles = release_json["roles_metadata"].keys()
        removed_role = old_roles[0]
        release_json["roles_metadata"].pop(removed_role)

        resp = self.app.put(
            reverse('ReleaseHandler',
                    kwargs={"obj_id": release_json["id"]}),
            jsonutils.dumps(release_json),
            headers=self.default_headers
        )
        new_roles = resp.json_body["roles_metadata"].keys()
        self.assertLess(len(new_roles), len(old_roles))
        self.assertNotIn(removed_role, new_roles)

    def test_roles_failed_to_delete_assigned(self):
        self.env.create(
            nodes_kwargs=[
                {"status": "ready", "roles": ["controller"]}
            ]
        )
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )

        release_json = resp.json_body[0]
        release_json["roles_metadata"].pop("controller")

        resp = self.app.put(
            reverse(
                'ReleaseHandler',
                kwargs={
                    "obj_id": release_json["id"]
                }
            ),
            jsonutils.dumps(release_json),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body["message"],
            "Cannot delete roles already assigned to nodes: controller"
        )
