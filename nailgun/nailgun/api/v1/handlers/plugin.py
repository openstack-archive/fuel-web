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

import pecan

from nailgun.api.v1.validators import plugin
from nailgun.api.v2.controllers.base import BaseController
from nailgun import objects


class PluginController(BaseController):

    single = objects.Plugin
    collection = objects.PluginCollection
    validator = plugin.PluginValidator

    @pecan.expose(template='json:', content_type='application/json')
    def post(self):
        """:returns: JSONized REST object.
        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 409 (object with such parameters already exists)
        """
        data = self.checked_data(self.validator.validate)
        obj = self.collection.single.get_by_name_version(
            data['name'], data['version'])
        if obj:
            raise self.http(409, self.collection.single.to_json(obj))
        return super(PluginController, self).post()
