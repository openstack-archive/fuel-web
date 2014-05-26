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

"""
Product info handlers
"""
import pecan

from nailgun.api.v2.controllers.base import BaseController
from nailgun.settings import settings


class VersionController(BaseController):
    """Version info handler
    """

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """:returns: FUEL/FUELWeb commit SHA, release version.
        :http: * 200 (OK)
        """
        return settings.VERSION
