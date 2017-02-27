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
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import validate


class BaseRemovedInHandler(BaseHandler):
    """Removed resource base handler"""

    @property
    def fuel_version(self):
        raise NotImplementedError

    @handle_errors
    @validate
    @serialize
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
    """Removed resource handler for Fuel 5.1"""
    fuel_version = "5.1"


class RemovedIn51RedHatAccountHandler(RemovedIn51Handler):
    pass


class RemovedIn51RedHatSetupHandler(RemovedIn51Handler):
    pass


class RemovedIn10Handler(BaseRemovedInHandler):
    """Removed resource handler for Fuel 10"""
    fuel_version = "10"

    @handle_errors
    @validate
    @serialize
    def GET(self, cluster_id):
        """A stub for the request. Always returns 410 with removed message.

        :http: 410 (Gone)
        :raises: webapi.Gone Exception
        :return: Removed in Fuel version message
        """
        message = u"Removed in Fuel version {0}".format(self.fuel_version)
        raise self.http(410, message)


class RemovedIn10VmwareAttributesDefaultsHandler(RemovedIn10Handler):
    pass


class RemovedIn10VmwareAttributesHandler(RemovedIn10Handler):
    pass
