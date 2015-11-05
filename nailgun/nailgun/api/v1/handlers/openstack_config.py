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
        return objects.OpenstackConfig.find_configs(
            web.input())

    @content
    def POST(self):
        data = self.checked_data()

        self.get_object_or_404(objects.Cluster, data['cluster_id'])
        if 'node_id' in data:
            self.get_object_or_404(objects.Node, data['node_id'])

        obj = objects.OpenstackConfig.create(data)
        return objects.OpenstackConfig.to_json(obj)


class OpenstackConfigHandler(SingleHandler):

    single = objects.OpenstackConfig
    validator = OpenstackConfigValidator

    def GET(self, obj_id):
        pass

    def DELETE(self, obj_id):
        pass


class OpenstackConfigExecuteHandler(BaseHandler):

    def PUT(self):
        pass
