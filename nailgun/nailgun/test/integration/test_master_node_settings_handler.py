#    Copyright 2014 Mirantis, Inc.
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

from nailgun.db.sqlalchemy.models import MasterNodeSettings

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse

from nailgun.openstack.common import jsonutils

from nailgun import objects


class TestMasterNodeSettingsHandler(BaseIntegrationTest):

    def test_get_controller(self):
        obj_id = self.db.query(MasterNodeSettings).one().id

        # should contain data that are defined in master_node_settings.json
        # fixture file which is located in fixtures directory for nailgun
        expected = {
            "id": obj_id,
            "settings": {
                "send_anonymous_statistic": True,
                "send_user_info": True,
                "user_info": {
                    "name": "Test User",
                    "company": "Test Company",
                    "email": "user@email.com"
                }
            }
        }

        resp = self.app.get(
            reverse("MasterNodeSettingsHandler", kwargs={"obj_id": obj_id}),
            headers=self.default_headers,
        )
        self.assertEqual(resp.json_body, expected)

    def test_put_controller(self):
        obj_id = self.db.query(MasterNodeSettings).one().id

        data = {
            "id": obj_id,
            "settings": {
                "send_anonymous_statistic": False,
                "send_user_info": True,
                "user_info": {
                    "name": "Some User",
                    "company": "Some Company",
                    "email": "user@email.com"
                }
            }
        }

        resp = self.app.put(
            reverse("MasterNodeSettingsHandler", kwargs={"obj_id": obj_id}),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )

        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json_body, data)

        settings_from_db = objects.MasterNodeSettings.get_by_uid(uid=obj_id)

        self.assertEqual(settings_from_db.settings, data["settings"])

    def test_patch_controller(self):
        obj_id = self.db.query(MasterNodeSettings).one().id

        data = {
            "settings": {
                "user_info": {
                    "name": "Test User",
                    "company": "Other Company"
                }
            }
        }

        expected = {
            "id": obj_id,
            "settings": {
                "send_anonymous_statistic": True,
                "send_user_info": True,
                "user_info": {
                    "name": "Test User",
                    "company": "Other Company",
                    "email": "user@email.com"
                }
            }
        }

        resp = self.app.patch(
            reverse("MasterNodeSettingsHandler", kwargs={"obj_id": obj_id}),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )

        self.assertEqual(200, resp.status_code)

        self.assertEqual(resp.json_body, expected)

        settings_from_db = objects.MasterNodeSettings.get_by_uid(obj_id)

        self.assertEqual(settings_from_db.settings, expected["settings"])

    def test_validation_error(self):
        obj_id = self.db.query(MasterNodeSettings).one().id

        data = {
            "settings": {
                "send_user_info": "I'm not boolean, bro:)"
            }
        }

        resp = self.app.put(
            reverse("MasterNodeSettingsHandler", kwargs={"obj_id": obj_id}),
            headers=self.default_headers,
            params=jsonutils.dumps(data),
            expect_errors=True
        )

        self.assertEqual(400, resp.status_code)
        self.assertIn("Failed validating", resp.body)

    def test_not_found_error(self):
        obj_id = self.db.query(MasterNodeSettings).one().id

        settings_from_db = objects.MasterNodeSettings.get_by_uid(obj_id)
        self.db.delete(settings_from_db)
        self.db.commit()

        resp = self.app.get(
            reverse("MasterNodeSettingsHandler", kwargs={"obj_id": obj_id}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(404, resp.status_code)
        self.assertIn("not found", resp.body)
