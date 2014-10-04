# -*- coding: utf-8 -*-

# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Handlers for removed resources
"""
from nailgun.api.v1.handlers.base import BaseHandler


class BaseRemovedIn(BaseHandler):
    """Removed resource base handler
    """
    @property
    def fuel_version(self):
        raise NotImplementedError

    GET = HEAD = POST = PUT = DELETE = lambda self: self._stub()

    def _stub(self):
        message = u"Removed in Fuel version {0}".format(self.fuel_version)
        raise self.http(410, message)


class RemovedIn51(BaseRemovedIn):
    fuel_version = "5.1"
