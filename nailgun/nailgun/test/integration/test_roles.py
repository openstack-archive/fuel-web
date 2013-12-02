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

import json

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

        release_json = json.loads(resp.body)[0]
        old_roles = set(release_json["roles"])
        release_json["roles"].append(test_role_name)

        resp = self.app.put(
            reverse('ReleaseHandler',
                    kwargs={"release_id": release_json["id"]}),
            json.dumps(release_json),
            headers=self.default_headers
        )
        new_roles = json.loads(resp.body)["roles"]
        self.assertIn(test_role_name, new_roles)
        self.assertLessEqual(old_roles, set(new_roles))

    def test_roles_delete(self):
        self.env.create_release()
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )

        release_json = json.loads(resp.body)[0]
        old_roles = release_json["roles"]
        release_json["roles"] = release_json["roles"][1:]

        resp = self.app.put(
            reverse('ReleaseHandler',
                    kwargs={"release_id": release_json["id"]}),
            json.dumps(release_json),
            headers=self.default_headers
        )
        new_roles = json.loads(resp.body)["roles"]
        self.assertLess(len(new_roles), len(old_roles))

    def test_roles_failed_to_delete_assigned(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"status": "ready", "roles": ["controller"]}
            ]
        )
        resp = self.app.get(
            reverse('ReleaseCollectionHandler'),
            headers=self.default_headers
        )

        release_json = json.loads(resp.body)[0]

        old_roles = set(release_json["roles"])
        old_roles.remove("controller")
        release_json["roles"] = list(old_roles)

        resp = self.app.put(
            reverse(
                'ReleaseHandler',
                kwargs={
                    "release_id": release_json["id"]
                }
            ),
            json.dumps(release_json),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status, 400)
        self.assertEqual(
            resp.body,
            "Cannot delete roles already assigned to nodes: controller"
        )
