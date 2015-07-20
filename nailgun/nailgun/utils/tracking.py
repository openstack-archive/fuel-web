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

import requests

from six.moves.urllib.parse import urljoin

from oslo_serialization import jsonutils

from nailgun.errors import errors
from nailgun.settings import settings


FAKE_REGISTRATION_FORM = {
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
                           "using public emails, such as "
                           "@gmail.com, @yahoo.com, etc.",
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

FAKE_LOGIN_FORM = {
    "credentials": {
        "metadata": {
            "label": "Login",
            "weight": 10
        },
        "email": {
            "type": "text",
            "label": "Mirantis Account Email",
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

FAKE_USER_INFO = {
    "name": "John Smith",
    "email": "john@smith.me",
    "company": "Company"
}

FAKE_RESTORE_PASSWORD_FORM = {
    "credentials": {
        "metadata": {
            "label": "Restore password",
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
    }
}


class FuelTrackingManager(object):

    FAKE_MODE = bool(settings.FAKE_TASKS)

    @classmethod
    def _url_for(cls, action):
        return urljoin(
            settings.MIRANTIS_REGISTRATION_URL,
            action
        )

    @classmethod
    def _do_request(cls, url, method="get", data=None, fake=None):
        if not cls.FAKE_MODE:
            try:
                req = getattr(requests, method)(
                    url,
                    data=jsonutils.dumps(data),
                    timeout=30,
                    headers={
                        "Content-Type": "application/json"
                    }
                )
            except Exception:
                raise errors.TrackingError(
                    "Failed to reach external server"
                )
            if req.status_code != 200:
                raise errors.TrackingError(
                    "Invalid response code received "
                    "from external server: {0}".format(req.status_code)
                )
            try:
                return req.json()
            except ValueError:
                raise errors.TrackingError(
                    "Invalid response received from external server"
                )
        return fake

    @classmethod
    def get_registration_form(cls):
        return cls._do_request(
            cls._url_for("registration"),
            "get",
            fake=FAKE_REGISTRATION_FORM
        )

    @classmethod
    def post_registration_form(cls, data):
        return cls._do_request(
            cls._url_for("registration"),
            "post",
            data=data,
            fake=FAKE_USER_INFO
        )

    @classmethod
    def get_login_form(cls):
        return cls._do_request(
            cls._url_for("login"),
            "get",
            fake=FAKE_LOGIN_FORM
        )

    @classmethod
    def post_login_form(cls, data):
        return cls._do_request(
            cls._url_for("login"),
            "post",
            data=data,
            fake=FAKE_USER_INFO
        )

    @classmethod
    def get_restore_password_form(cls):
        return cls._do_request(
            cls._url_for("restore_password"),
            "get",
            fake=FAKE_RESTORE_PASSWORD_FORM
        )

    @classmethod
    def post_restore_password_form(cls, data):
        return cls._do_request(
            cls._url_for("restore_password"),
            "post",
            data=data,
            fake={}
        )
