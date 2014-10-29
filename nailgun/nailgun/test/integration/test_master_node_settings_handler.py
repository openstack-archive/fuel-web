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

import unittest2

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse

from nailgun.openstack.common import jsonutils

from nailgun import objects


class TestMasterNodeSettingsHandler(BaseIntegrationTest):

    @unittest2.skip('To be reworked')
    def test_get_controller(self):
        # should contain data that are defined in master_node_settings.yaml
        # fixture file which is located in fixtures directory for nailgun
        expected = {
            "settings": {
                "statistics": {
                    "send_anonymous_statistic": {
                        "type": "checkbox",
                        "value": True,
                        "label": "statistics.setting_labels."
                                 "send_anonymous_statistic",
                        "weight": 10
                    },
                    "send_user_info": {
                        "type": "checkbox",
                        "value": True,
                        "label": "statistics.setting_labels.send_user_info",
                        "weight": 20,
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "name": {
                        "type": "text",
                        "value": "",
                        "label": "statistics.setting_labels.name",
                        "weight": 30,
                        "regex": {
                            "source": "\S",
                            "error": "statistics.errors.name"
                        },
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "fuel_settings:statistics."
                            "send_user_info.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "email": {
                        "type": "text",
                        "value": "",
                        "label": "statistics.setting_labels.email",
                        "weight": 40,
                        "regex": {
                            "source": "\S",
                            "error": "statistics.errors.email"
                        },
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "fuel_settings:statistics."
                            "send_user_info.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "company": {
                        "type": "text",
                        "value": "",
                        "label": "statistics.setting_labels.company",
                        "weight": 50,
                        "regex": {
                            "source": "\S",
                            "error": "statistics.errors.company"
                        },
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "fuel_settings:statistics."
                            "send_user_info.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "user_choice_saved": {
                        "type": "hidden",
                        "value": False
                    }
                }
            }
        }

        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
        )
        self.assertEqual(resp.json_body, expected)

    @unittest2.skip('To be reworked')
    def test_put_controller(self):
        data = {
            "settings": {
                "statistics": {
                    "send_anonymous_statistic": {
                        "type": "checkbox",
                        "value": False,
                        "label": "statistics.setting_labels."
                                 "send_anonymous_statistic",
                        "weight": 10
                    },
                    "send_user_info": {
                        "type": "checkbox",
                        "value": True,
                        "label": "statistics.setting_labels.send_user_info",
                        "weight": 20,
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "name": {
                        "type": "text",
                        "value": "Some User",
                        "label": "statistics.setting_labels.name",
                        "weight": 30,
                        "regex": {
                            "source": "\S",
                            "error": "statistics.errors.name"
                        },
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "fuel_settings:statistics."
                            "send_user_info.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "email": {
                        "type": "text",
                        "value": "user@email.com",
                        "label": "statistics.setting_labels.email",
                        "weight": 40,
                        "regex": {
                            "source": "\S",
                            "error": "statistics.errors.email"
                        },
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "fuel_settings:statistics."
                            "send_user_info.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "company": {
                        "type": "text",
                        "value": "Some Company",
                        "label": "statistics.setting_labels.company",
                        "weight": 50,
                        "regex": {
                            "source": "\S",
                            "error": "statistics.errors.company"
                        },
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "fuel_settings:statistics."
                            "send_user_info.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "user_choice_saved": {
                        "type": "hidden",
                        "value": True
                    }
                }
            }
        }

        resp = self.app.put(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )

        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json_body, data)

        settings_from_db = objects.MasterNodeSettings.get_one()

        self.assertEqual(settings_from_db.settings, data["settings"])

    @unittest2.skip('To be reworked')
    def test_patch_controller(self):
        data = {
            "settings": {
                "statistics": {
                    "company": {
                        "value": "Other Company"
                    }
                }
            }
        }

        expected = {
            "settings": {
                "statistics": {
                    "send_anonymous_statistic": {
                        "type": "checkbox",
                        "value": True,
                        "label": "statistics.setting_labels."
                                 "send_anonymous_statistic",
                        "weight": 10
                    },
                    "send_user_info": {
                        "type": "checkbox",
                        "value": True,
                        "label": "statistics.setting_labels.send_user_info",
                        "weight": 20,
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "name": {
                        "type": "text",
                        "value": "",
                        "label": "statistics.setting_labels.name",
                        "weight": 30,
                        "regex": {
                            "source": "\S",
                            "error": "statistics.errors.name"
                        },
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "fuel_settings:statistics."
                            "send_user_info.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "email": {
                        "type": "text",
                        "value": "",
                        "label": "statistics.setting_labels.email",
                        "weight": 40,
                        "regex": {
                            "source": "\S",
                            "error": "statistics.errors.email"
                        },
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "fuel_settings:statistics."
                            "send_user_info.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "company": {
                        "type": "text",
                        "value": "Other Company",
                        "label": "statistics.setting_labels.company",
                        "weight": 50,
                        "regex": {
                            "source": "\S",
                            "error": "statistics.errors.company"
                        },
                        "restrictions": [
                            "fuel_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "fuel_settings:statistics."
                            "send_user_info.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "user_choice_saved": {
                        "type": "hidden",
                        "value": False
                    }
                }
            }
        }

        resp = self.app.patch(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
            params=jsonutils.dumps(data)
        )

        self.assertEqual(200, resp.status_code)

        self.assertEqual(resp.json_body, expected)

        settings_from_db = objects.MasterNodeSettings.get_one()

        self.assertEqual(settings_from_db.settings, expected["settings"])

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
        self.assertIn("Failed validating", resp.body)

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
        self.assertIn("not found", resp.body)
