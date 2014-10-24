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

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse

from nailgun.openstack.common import jsonutils

from nailgun import objects


class TestMasterNodeSettingsHandler(BaseIntegrationTest):

    def test_get_controller(self):
        # should contain data that are defined in master_node_settings.yaml
        # fixture file which is located in fixtures directory for nailgun
        expected = {
            "settings": {
                "statistics": {
                    "metadata": {
                        "weight": 10
                    },
                    "send_anonymous_statistic": {
                        "type": "checkbox",
                        "value": True,
                        "label": "Send usage statistics to Mirantis",
                        "weight": 10
                    },
                    "send_user_info": {
                        "type": "checkbox",
                        "value": True,
                        "label": "Identify my error reports so that "
                                 "Mirantis Support can assist me",
                        "weight": 20,
                        "restrictions": [
                            "master_node_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "show_welcome_page": {
                        "type": "hidden",
                        "value": True
                    }
                },
                "user_info": {
                    "metadata": {
                        "weight": 20,
                        "restrictions": [
                            "master_node_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "master_node_settings:statistics."
                            "send_user_info.value == false",
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
                        "label": "Name",
                        "weight": 10,
                        "regex": {
                            "source": "\S",
                            "error": "Please fill your name"
                        }
                    },
                    "email": {
                        "type": "text",
                        "value": "",
                        "label": "Email",
                        "weight": 20,
                        "regex": {
                            "source": "\S",
                            "error": "Please fill email address"
                        }
                    },
                    "company": {
                        "type": "text",
                        "value": "",
                        "label": "Company",
                        "weight": 30,
                        "regex": {
                            "source": "\S",
                            "error": "Please fill company name"
                        }
                    }
                }
            }
        }

        resp = self.app.get(
            reverse("MasterNodeSettingsHandler"),
            headers=self.default_headers,
        )
        self.assertEqual(resp.json_body, expected)

    def test_put_controller(self):
        data = {
            "settings": {
                "statistics": {
                    "metadata": {
                        "weight": 10
                    },
                    "send_anonymous_statistic": {
                        "type": "checkbox",
                        "value": False,
                        "label": "Send usage statistics to Mirantis",
                        "weight": 10
                    },
                    "send_user_info": {
                        "type": "checkbox",
                        "value": True,
                        "label": "Identify my error reports so that "
                                 "Mirantis Support can assist me",
                        "weight": 20,
                        "restrictions": [
                            "master_node_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "show_welcome_page": {
                        "type": "hidden",
                        "value": False
                    }
                },
                "user_info": {
                    "metadata": {
                        "weight": 20,
                        "restrictions": [
                            "master_node_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "master_node_settings:statistics."
                            "send_user_info.value == false",
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
                        "label": "Name",
                        "weight": 10,
                        "regex": {
                            "source": "\S",
                            "error": "Please fill your name"
                        }
                    },
                    "email": {
                        "type": "text",
                        "value": "user@email.com",
                        "label": "Email",
                        "weight": 20,
                        "regex": {
                            "source": "\S",
                            "error": "Please fill email address"
                        }
                    },
                    "company": {
                        "type": "text",
                        "value": "Some Company",
                        "label": "Company",
                        "weight": 30,
                        "regex": {
                            "source": "\S",
                            "error": "Please fill company name"
                        }
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

    def test_patch_controller(self):
        data = {
            "settings": {
                "user_info": {
                    "company": {
                        "value": "Other Company"
                    }
                }
            }
        }

        expected = {
            "settings": {
                "statistics": {
                    "metadata": {
                        "weight": 10
                    },
                    "send_anonymous_statistic": {
                        "type": "checkbox",
                        "value": True,
                        "label": "Send usage statistics to Mirantis",
                        "weight": 10
                    },
                    "send_user_info": {
                        "type": "checkbox",
                        "value": True,
                        "label": "Identify my error reports so that "
                                 "Mirantis Support can assist me",
                        "weight": 20,
                        "restrictions": [
                            "master_node_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            {
                                "condition":
                                "not ('mirantis' in version:feature_groups)",
                                "action": "hide"
                            }
                        ]
                    },
                    "show_welcome_page": {
                        "type": "hidden",
                        "value": True
                    }
                },
                "user_info": {
                    "metadata": {
                        "weight": 20,
                        "restrictions": [
                            "master_node_settings:statistics."
                            "send_anonymous_statistic.value == false",
                            "master_node_settings:statistics."
                            "send_user_info.value == false",
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
                        "label": "Name",
                        "weight": 10,
                        "regex": {
                            "source": "\S",
                            "error": "Please fill your name"
                        }
                    },
                    "email": {
                        "type": "text",
                        "value": "",
                        "label": "Email",
                        "weight": 20,
                        "regex": {
                            "source": "\S",
                            "error": "Please fill email address"
                        }
                    },
                    "company": {
                        "type": "text",
                        "value": "Other Company",
                        "label": "Company",
                        "weight": 30,
                        "regex": {
                            "source": "\S",
                            "error": "Please fill company name"
                        }
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
            "settings": {
                "send_user_info": "I'm not an object, bro:)"
            }
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
