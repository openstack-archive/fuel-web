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

from sqlalchemy.exc import IntegrityError

from nailgun.db.sqlalchemy.models import Role
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestRoles(BaseIntegrationTest):

    def test_roles_update(self):
        self.env.create_release()
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )
        test_role_name = "testrole"

        release_json = resp.json_body[0]
        old_roles = set(release_json["roles"])
        release_json["roles"].append(test_role_name)

        resp = self.app.put(
            reverse('ReleaseHandler',
                    kwargs={"obj_id": release_json["id"]}),
            jsonutils.dumps(release_json),
            headers=self.default_headers
        )
        new_roles = resp.json_body["roles"]
        self.assertIn(test_role_name, new_roles)
        self.assertLessEqual(old_roles, set(new_roles))

    def test_roles_add_and_remove(self):
        self.env.create_release()
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )
        test_role_name = "testrole"

        release_json = resp.json_body[0]
        old_roles = release_json["roles"]
        release_json["roles"].append(test_role_name)
        release_json["roles"].remove(old_roles[0])
        expected_roles = list(release_json["roles"])

        resp = self.app.put(
            reverse('ReleaseHandler',
                    kwargs={"obj_id": release_json["id"]}),
            jsonutils.dumps(release_json),
            headers=self.default_headers
        )
        new_roles = resp.json_body["roles"]
        self.assertEqual(expected_roles, new_roles)

    def test_roles_add_duplicated_through_handler(self):
        self.env.create_release()
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )
        test_role_name = "testrole"

        release_json = resp.json_body[0]
        old_roles = release_json["roles"]
        release_json["roles"].append(test_role_name)
        expected_roles = list(release_json["roles"])
        # add some duplicates
        release_json["roles"].extend(old_roles)

        resp = self.app.put(
            reverse('ReleaseHandler',
                    kwargs={"obj_id": release_json["id"]}),
            jsonutils.dumps(release_json),
            headers=self.default_headers
        )
        new_roles = resp.json_body["roles"]
        self.assertEqual(expected_roles, new_roles)

    def test_roles_add_duplicated_to_db_directly(self):
        self.env.create_release()
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )
        release_json = resp.json_body[0]
        old_roles = list(release_json["roles"])

        role = Role(name=old_roles[0],
                    release_id=release_json["id"])
        added = True
        try:
            self.db.add(role)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            added = False
        self.assertFalse(added)

        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )
        release_json = resp.json_body[0]
        new_roles = list(release_json["roles"])
        self.assertEqual(old_roles, new_roles)

    def test_roles_delete(self):
        self.env.create_release()
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )

        release_json = resp.json_body[0]
        old_roles = release_json["roles"]
        removed_role = release_json["roles"][0]
        release_json["roles"] = release_json["roles"][1:]

        resp = self.app.put(
            reverse('ReleaseHandler',
                    kwargs={"obj_id": release_json["id"]}),
            jsonutils.dumps(release_json),
            headers=self.default_headers
        )
        new_roles = resp.json_body["roles"]
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

        old_roles = set(release_json["roles"])
        old_roles.remove("controller")
        release_json["roles"] = list(old_roles)

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
            resp.body,
            "Cannot delete roles already assigned to nodes: controller"
        )
