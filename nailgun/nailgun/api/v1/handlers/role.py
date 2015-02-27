# -*- coding: utf-8 -*-

# Copyright 2015 Mirantis, Inc.
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


from nailgun.api.v1.handlers import base

from nailgun import objects


class RoleHandler(base.SingleHandler):

    single = objects.Role

    def GET(self, release_id, role_id):
        role = self.single.get(release_id, role_id)
        return self.single.to_json(role)

    def POST(self, release_id):
        data = self.checked_data()
        role = self.single.create(release_id, data)
        return self.single.to_json(role)

    def PUT(self, release_id, role_id):
        role = self.single.get(release_id, role_id)
        data = self.checked_data()
        role = self.single.update(role, data)
        return self.single.to_json(role)

    def DELETE(self, release_id, role_id):
        role = self.single.get(release_id, role_id)
        self.single.delete(role)
