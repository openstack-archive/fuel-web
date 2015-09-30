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

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.validators.base import BasicValidator

from nailgun.errors import errors

from nailgun.utils.tracking import FuelTrackingManager


class FuelRegistrationForm(BaseHandler):
    """Registration form handler"""

    validator = BasicValidator

    @content
    def GET(self):
        """Returns Fuel registration form

        :returns: JSON representation of registration form
        :http: * 200 (OK)
        """
        try:
            return FuelTrackingManager.get_registration_form()
        except errors.TrackingError as exc:
            raise self.http(400, exc.message)

    @content
    def POST(self):
        json_data = self.checked_data()
        try:
            return FuelTrackingManager.post_registration_form(json_data)
        except errors.TrackingError as exc:
            raise self.http(400, exc.message)


class FuelLoginForm(BaseHandler):
    """Login form handler"""

    validator = BasicValidator

    @content
    def GET(self):
        """Returns Fuel login form

        :returns: JSON representation of login form
        :http: * 200 (OK)
        """
        try:
            return FuelTrackingManager.get_login_form()
        except errors.TrackingError as exc:
            raise self.http(400, exc.message)

    @content
    def POST(self):
        json_data = self.checked_data()
        try:
            return FuelTrackingManager.post_login_form(json_data)
        except errors.TrackingError as exc:
            raise self.http(400, exc.message)


class FuelRestorePasswordForm(BaseHandler):
    """Restore password form handler"""

    validator = BasicValidator

    @content
    def GET(self):
        """Returns Fuel restore password form

        :returns: JSON representation of restore password form
        :http: * 200 (OK)
        """
        try:
            return FuelTrackingManager.get_restore_password_form()
        except errors.TrackingError as exc:
            raise self.http(400, exc.message)

    @content
    def POST(self):
        json_data = self.checked_data()
        try:
            return FuelTrackingManager.post_restore_password_form(json_data)
        except errors.TrackingError as exc:
            raise self.http(400, exc.message)
