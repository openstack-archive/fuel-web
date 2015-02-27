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
from nailgun.api.v1.validators.role import RoleValidator
from nailgun import objects
from nailgun.errors import errors


class RoleHandler(base.SingleHandler):

    single = objects.Role
    validator = RoleValidator

    def get_role_or_404(self, release_id, role_name):
        role = self.single.get_by_release_id_role_name(release_id, role_name)
        if role is None:
            raise self.http(
                404,
                u'Role {name} for release {release} is not found'.format(
                    release_id, role_name)
        return role

    def GET(self, release_id, role_name):
        role = self.get_role_or_404(release_id, role_name)
        return self.single.to_json(role)

    def PUT(self, release_id, role_name):
        role = self.get_role_or_404(release_id, role_name)
        data = self.checked_data(instance=role)

        updated = self.single.update(role, data)
        return self.single.to_json(updated)

    def DELETE(self, release_id, role_name):
        role = self.get_role_or_404(release_id, role_name)

        try:
            self.validator.validate_delete(role)
        except errors.CannotDelete as exc:
            raise self.http(400, exc.message)

        self.single.delete(role)
        raise self.http(204)


class RoleCollectionHandler(base.CollectionHandler):

    single = objects.Role
    collection = objects.RoleCollection
    validator = RoleValidator

    def POST(self, release_id):
        release = self.get_object_or_404(objects.Release, release_id)
        data = self.checked_data()
        role = self.single.create(release, data)
        raise self.http(201, self.single.to_json(role))

    def GET(self, release_id):
        release = self.get_object_or_404(objects.Release, release_id)
        return self.collection.to_json(release.roles)
