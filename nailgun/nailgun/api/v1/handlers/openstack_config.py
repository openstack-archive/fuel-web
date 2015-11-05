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

import web

from nailgun.api.v1.handlers.base import content

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import SingleHandler

from nailgun.api.v1.validators.openstack_config import OpenstackConfigValidator

from nailgun import objects


class OpenstackConfigsHandler(BaseHandler):

    validator = OpenstackConfigValidator

    @content
    def GET(self):
        """Returns list of config objects filtered by specified filters in
        URL query.

        :http: * 200 (OK)
               * 400 (Invalid query specified)
        :return: List of config objects in JSON format.
        """
        data = self.checked_data(
            self.validator.validate_query, data=web.input())
        return objects.OpenstackConfig.find_configs(data)

    @content
    def POST(self):
        """Creates new config object.

         If config object with specified parameters exists, it is replaced
         with a new config object. Previous object is marked as inactive.
         It can be retrieved to track the history of configuration changes.

        :http: * 201 (Object successfully created)
               * 400 (Invalid query specified)
               * 404 (Object dependencies not found)
        :reutrn: New config object in JSON format.
        """
        data = self.checked_data()

        self.get_object_or_404(objects.Cluster, data['cluster_id'])
        if 'node_id' in data:
            self.get_object_or_404(objects.Node, data['node_id'])

        obj = objects.OpenstackConfig.create(data)
        return self.http(201, objects.OpenstackConfig.to_json(obj))


class OpenstackConfigHandler(SingleHandler):

    single = objects.OpenstackConfig
    validator = OpenstackConfigValidator


class OpenstackConfigExecuteHandler(BaseHandler):

    def PUT(self):
        """Executes update tasks for specified resources.

        :http: * 200 (OK)
        """
        pass
