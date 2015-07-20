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

import copy

from oslo_serialization import jsonutils

from nailgun import objects
from nailgun.statistics.fuel_statistics.installation_info \
    import InstallationInfo
from nailgun.test.base import BaseMasterNodeSettignsTest
from nailgun.utils import reverse


class TestMasterNodeSettingsHandler(BaseMasterNodeSettignsTest):

    def test_get_controller(self):
        expected = self.master_node_settings

        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers
        )
        self.assertDictEqual(resp.json_body, expected)

    def test_put(self):
        data = copy.deepcopy(self.master_node_settings)

        data['settings']['statistics']['send_user_info']['value'] = True

        resp = self.app.put(
            reverse('MasterNodeSettingsHandler'),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(resp.json_body, data)

    def test_patch(self):
        data = copy.deepcopy(self.master_node_settings)
        user_info = data['settings']['statistics']['send_user_info']
        user_info['value'] = True

        resp = self.app.patch(
            reverse('MasterNodeSettingsHandler'),
            headers=self.default_headers,
            params=jsonutils.dumps({
                'settings': {
                    'statistics': {
                        'send_user_info': user_info,
                    }
                }
            })
        )

        self.assertEqual(200, resp.status_code)

        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers
        )
        self.assertItemsEqual(resp.json_body, data)

    def test_delete(self):
        resp = self.app.delete(
            reverse('MasterNodeSettingsHandler'),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(405, resp.status_code)

    def test_validate_ok(self):
        data = {
            "settings": {},
        }

        resp = self.app.put(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )

        self.assertEqual(200, resp.status_code)

    def test_validation_error(self):
        data = {
            "settings": "I'm not an object, bro:)"
        }

        resp = self.app.put(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            params=jsonutils.dumps(data),
            expect_errors=True
        )

        self.assertEqual(400, resp.status_code)

    def test_master_uid_change_error(self):
        data = {
            'master_node_uid': 'xxx',
        }

        resp = self.app.put(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            params=jsonutils.dumps(data),
            expect_errors=True
        )

        self.assertEqual(200, resp.status_code)
        settings_from_db = objects.MasterNodeSettings.get_one()
        self.assertEqual(settings_from_db.master_node_uid,
                         self.master_node_settings['master_node_uid'])

    def test_not_found_error(self):
        settings_from_db = objects.MasterNodeSettings.get_one()
        self.db.delete(settings_from_db)
        self.db.commit()

        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(404, resp.status_code)

    def test_stats_sending_enabled(self):
        self.assertEqual(objects.MasterNodeSettings.must_send_stats(), False)

        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        data = resp.json_body

        # emulate user confirmed settings in UI
        data["settings"]["statistics"]["user_choice_saved"]["value"] = True
        resp = self.app.put(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )
        self.assertEqual(200, resp.status_code)
        self.assertTrue(objects.MasterNodeSettings.must_send_stats())

        # emulate user disabled statistics sending
        data["settings"]["statistics"]["send_anonymous_statistic"]["value"] = \
            False
        resp = self.app.put(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )
        self.assertEqual(200, resp.status_code)
        self.assertFalse(objects.MasterNodeSettings.must_send_stats())

    def test_user_contacts_info_disabled_while_not_confirmed_by_user(self):
        self.assertDictEqual(
            InstallationInfo().get_installation_info()['user_information'],
            {'contact_info_provided': False})

    def test_user_contacts_info_disabled_by_default(self):
        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        data = resp.json_body

        # emulate user confirmed settings in UI
        data["settings"]["statistics"]["user_choice_saved"]["value"] = True
        resp = self.app.put(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )
        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(
            InstallationInfo().get_installation_info()['user_information'],
            {'contact_info_provided': False})

    def test_user_contacts_info_enabled_by_user(self):
        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        data = resp.json_body

        # emulate user enabled contact info sending to support team
        data["settings"]["statistics"]["user_choice_saved"]["value"] = True
        data["settings"]["statistics"]["send_user_info"]["value"] = \
            True
        name = "user"
        email = "u@e.mail"
        company = "user company"
        data["settings"]["statistics"]["name"]["value"] = name
        data["settings"]["statistics"]["email"]["value"] = email
        data["settings"]["statistics"]["company"]["value"] = company
        resp = self.app.put(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )
        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(
            InstallationInfo().get_installation_info()['user_information'],
            {
                'contact_info_provided': True,
                'name': name,
                'email': email,
                'company': company
            }
        )

    def test_partial_user_contacts_info(self):
        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        data = resp.json_body

        # emulate user enabled contact info sending to support team
        data["settings"]["statistics"]["user_choice_saved"]["value"] = True
        data["settings"]["statistics"]["send_user_info"]["value"] = \
            True
        name = "user"
        email = "u@e.mail"
        data["settings"]["statistics"]["name"]["value"] = name
        data["settings"]["statistics"]["email"]["value"] = email
        resp = self.app.put(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )
        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(
            InstallationInfo().get_installation_info()['user_information'],
            {
                'contact_info_provided': True,
                'name': name,
                'email': email,
                'company': ''
            }
        )

    def test_user_contacts_info_broken(self):
        settings_from_db = objects.MasterNodeSettings.get_one()
        settings = dict(settings_from_db.settings)
        settings["statistics"] = None
        settings_from_db.settings = settings
        self.db.commit()

        self.assertDictEqual(
            InstallationInfo().get_installation_info()['user_information'],
            {'contact_info_provided': False})

    def test_installation_info_when_stats_info_deleted(self):
        settings_from_db = objects.MasterNodeSettings.get_one()
        self.db.delete(settings_from_db)
        self.db.commit()

        self.assertDictEqual(
            InstallationInfo().get_installation_info()['user_information'],
            {'contact_info_provided': False})
        self.assertIsNone(
            InstallationInfo().get_installation_info()['master_node_uid'])
