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
Product info handlers
"""

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import content
from nailgun.settings import settings
from nailgun import utils


class VersionHandler(BaseHandler):
    """Version info handler
    """

    release_versions = "/etc/fuel/release_versions/*.yaml"

    @content
    def GET(self):
        """:returns: FUEL/FUELWeb commit SHA, release version.
        :http: * 200 (OK)
        """
        version = settings.VERSION
        method = settings.AUTH['AUTHENTICATION_METHOD']
        version['auth_required'] = method in ['fake', 'keystone']

        version['release_versions'] = utils.get_fuel_release_versions(
            self.release_versions)
        return version
