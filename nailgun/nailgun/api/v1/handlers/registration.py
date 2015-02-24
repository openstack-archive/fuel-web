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

"""
Product registration handlers
"""

import web


from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content

from nailgun.openstack.common import jsonutils


class FuelRegistrationForm(BaseHandler):
    """Registration form handler"""

    @content
    def GET(self):
        """Returns Fuel registration form
        :returns: JSON representation of registration form
        :http: * 200 (OK)
        """
        return {
            "credentials": {
                "metadata": {
                    "label": "Sign Up",
                    "weight": 10
                },
                "first_name": {
                    "type": "text",
                    "label": "First Name",
                    "value": "",
                    "weight": 10,
                    "regex": {
                        "source": "\\S",
                        "error": "First name should not be empty"
                    }
                },
                "last_name": {
                    "type": "text",
                    "label": "Last Name",
                    "value": "",
                    "weight": 20
                },
                "email": {
                    "type": "text",
                    "label": "Corporate email",
                    "value": "",
                    "weight": 30,
                    "description": "For best experience please avoid "
                                   "using public emails, such as @gmail.com, "
                                   "@yahoo.com, etc.",
                    "regex": {
                        "source": "^\\S+@\\S+$",
                        "error": "Invalid email"
                    }
                },
                "company": {
                    "type": "text",
                    "label": "Company",
                    "value": "",
                    "weight": 40,
                    "regex": {
                        "source": "\\S",
                        "error": "Company should not be empty"
                    }
                },
                "phone": {
                    "type": "text",
                    "label": "Phone number",
                    "value": "",
                    "weight": 50
                },
                "job": {
                    "type": "text",
                    "label": "Job Title",
                    "value": "",
                    "weight": 60
                },
                "country": {
                    "type": "select",
                    "label": "Select Country",
                    "value": "us",
                    "weight": 70,
                    "values": [
                        {
                            "data": "us",
                            "label": "US && Canada"
                        }
                    ]
                },
                "region": {
                    "type": "select",
                    "label": "US & Canade State/Province",
                    "value": "",
                    "weight": 80,
                    "values": [
                        {
                            "data": "Alabama",
                            "label": "Alabama"
                        }
                    ]
                },
                "agree": {
                    "type": "checkbox",
                    "value": "",
                    "label": "I Read and Accept Terms & Conditions",
                    "description": "https://software.mirantis.com/"
                                   "blank/terms-and-conditions/"
                }
            }
        }

    @content
    def POST(self):
        data = web.data()
        try:
            json_data = jsonutils.loads(data)
        except Exception:
            raise self.http(400, "Invalid JSON received")

        if json_data["credentials"]["first_name"]["value"] == "Darth":
            raise self.http(
                400,
                jsonutils.dumps({
                    "message": "Death Star destroyed is",
                    "errors": [
                        {"field": "first_name", "message": "Yoda disapproves"}
                    ]
                })
            )

        if json_data["credentials"]["email"]["value"] \
                == "gmail@chucknorris.com":
            raise self.http(
                400,
                jsonutils.dumps({
                    "message": "Godmode disabled",
                    "errors": [
                        {
                            "field": "email",
                            "message": "Chuck, you don't need to register"
                        },
                        {"field": "first_name", "message": "Really?"}
                    ]
                })
            )
        return {}


class FuelLoginForm(BaseHandler):
    """Login form handler"""

    @content
    def GET(self):
        """Returns Fuel registration form
        :returns: JSON representation of registration form
        :http: * 200 (OK)
        """
        return {
            "credentials": {
                "metadata": {
                    "label": "Login",
                    "weight": 10
                },
                "email": {
                    "type": "text",
                    "label": "Email",
                    "value": "",
                    "weight": 10,
                    "regex": {
                        "source": "^\\S+@\\S+$",
                        "error": "Invalid email"
                    }
                },
                "password": {
                    "type": "password",
                    "label": "Password",
                    "value": "",
                    "weight": 20,
                    "regex": {
                        "source": "\\S",
                        "error": "Password cannot be empty"
                    }
                }
            }
        }

    @content
    def POST(self):
        return {}
