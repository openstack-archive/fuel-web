# -*- coding: utf-8 -*-
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
import functools
import mock

from oslo_serialization import jsonutils

from nailgun import objects
from nailgun.statistics.fuel_statistics.installation_info \
    import InstallationInfo
from nailgun.test.base import BaseMasterNodeSettignsTest
from nailgun.utils import reverse


class TestMasterNodeSettingsHandler(BaseMasterNodeSettignsTest):

    def setUp(self):
        self.patcher = mock.patch(
            'nailgun.statistics.fuel_statistics.installation_info'
            '.InstallationInfo.fuel_packages_info', return_value=[])
        self.patcher.start()
        super(TestMasterNodeSettingsHandler, self).setUp()

    def tearDown(self):
        super(TestMasterNodeSettingsHandler, self).tearDown()
        self.patcher.stop()

    def test_get_controller(self):
        expected = self.master_node_settings

        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers
        )
        self.assertDictEqual(resp.json_body, expected)

    def test_put(self):
        data = copy.deepcopy(self.master_node_settings)

        data['settings']['statistics'][
            'send_anonymous_statistic']['value'] = True

        resp = self.app.put(
            reverse('MasterNodeSettingsHandler'),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )

        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(resp.json_body, data)

    def test_patch(self):
        data = copy.deepcopy(self.master_node_settings)
        send_stat = data['settings']['statistics']['send_anonymous_statistic']
        send_stat['value'] = True

        resp = self.app.patch(
            reverse('MasterNodeSettingsHandler'),
            headers=self.default_headers,
            params=jsonutils.dumps({
                'settings': {
                    'statistics': {
                        'send_anonymous_statistic': send_stat,
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
            "settings": {
                "ui_settings": {
                    "view_mode": "standard",
                    "filter": {},
                    "sort": [{"status": "asc"}],
                    "filter_by_labels": {},
                    "sort_by_labels": [],
                    "search": ""
                }
            },
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

    def test_installation_info_when_stats_info_deleted(self):
        settings_from_db = objects.MasterNodeSettings.get_one()
        self.db.delete(settings_from_db)
        self.db.commit()

        self.assertDictEqual(
            InstallationInfo().get_installation_info()['user_information'],
            {'contact_info_provided': False})
        self.assertIsNone(
            InstallationInfo().get_installation_info()['master_node_uid'])

    def get_current_settings(self):
        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        return resp.json_body

    def check_task_created_only_on_new_opt_in(self, handler_method):

        def get_settings_value(data, setting_name):
            return data['settings']['statistics'][setting_name]['value']

        def set_settings_value(data, setting_name, value):
            data['settings']['statistics'][setting_name]['value'] = value

        with mock.patch('nailgun.api.v1.handlers.master_node_settings.'
                        'MasterNodeSettingsHandler._handle_stats_opt_in'
                        ) as task_creator:

            # Checking called on enabling sending
            data = self.get_current_settings()
            self.assertFalse(get_settings_value(data, 'user_choice_saved'))
            set_settings_value(data, 'user_choice_saved', True)
            resp = handler_method(params=jsonutils.dumps(data))
            self.assertEqual(200, resp.status_code)
            self.assertEqual(1, task_creator.call_count)

            # Checking not called on same value
            data = self.get_current_settings()
            self.assertTrue(get_settings_value(data, 'user_choice_saved'))
            resp = handler_method(params=jsonutils.dumps(data))
            self.assertEqual(200, resp.status_code)
            self.assertEqual(1, task_creator.call_count)

            # Checking called on another opt in value
            data = self.get_current_settings()
            self.assertTrue(get_settings_value(data, 'user_choice_saved'))
            opt_in = get_settings_value(data, 'send_anonymous_statistic')
            set_settings_value(data, 'send_anonymous_statistic', not opt_in)
            resp = handler_method(params=jsonutils.dumps(data))
            self.assertEqual(200, resp.status_code)
            self.assertEqual(2, task_creator.call_count)

    def test_task_created_only_on_put_new_opt_in(self):
        handler_method = functools.partial(
            self.app.put, reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers)
        self.check_task_created_only_on_new_opt_in(handler_method)

    def test_task_created_only_on_patch_new_opt_in(self):
        handler_method = functools.partial(
            self.app.patch, reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers)
        self.check_task_created_only_on_new_opt_in(handler_method)
