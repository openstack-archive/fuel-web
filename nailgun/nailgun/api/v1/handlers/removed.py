# -*- coding: utf-8 -*-

# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
Handlers for removed resources
"""
from nailgun.api.v1.handlers.base import BaseHandler


class BaseRemovedInHandler(BaseHandler):
    """Removed resource base handler
    """

    @property
    def fuel_version(self):
        raise NotImplementedError

    def GET(self):
        """A stub for the request. Always returns 410 with removed message.

        :http: 410 (Gone)
        :raises: webapi.Gone Exception
        :return: Removed in Fuel version message
        """
        message = u"Removed in Fuel version {0}".format(self.fuel_version)
        raise self.http(410, message)

    HEAD = POST = PUT = DELETE = GET


class RemovedIn51Handler(BaseRemovedInHandler):
    """Removed resource handler for Fuel 5.1
    """
    fuel_version = "5.1"


class RemovedIn51RedHatAccountHandler(RemovedIn51Handler):
    pass


class RemovedIn51RedHatSetupHandler(RemovedIn51Handler):
    pass
