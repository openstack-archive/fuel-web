# -*- coding: utf-8 -*-

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

import pecan

from nailgun.api.v1.validators.role import RoleValidator
from nailgun.api.v2.controllers.base import BaseController
from nailgun.errors import errors
from nailgun import objects


class RoleController(BaseController):

    single = objects.Role
    collection = objects.RoleCollection
    validator = RoleValidator

    def get_role_or_404(self, release_id, role_name):
        role = self.single.get_by_release_id_role_name(release_id, role_name)
        if role is None:
            raise self.http(
                404,
                u'Role {name} for release {release} is not found'.format(
                    release=release_id, name=role_name))
        return role

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self, release_id):
        """:http:
            * 200 (OK)
        """
        release = self.get_object_or_404(objects.Release, release_id)
        return self.collection.to_list(release.role_list)

    @pecan.expose(template='json:', content_type='application/json')
    def get_one(self, release_id, role_name):
        """:http:
            * 200 (OK)
            * 404 (no such object found)
        """
        role = self.get_role_or_404(release_id, role_name)
        return self.single.to_dict(role)

    @pecan.expose(template='json:', content_type='application/json')
    def post(self, release_id):
        """:http:
            * 201 (object successfully created)
            * 400 (invalid object data specified)
            * 409 (object with such parameters already exists)
        """
        data = self.checked_data()
        role_name = data['name']

        role = self.single.get_by_release_id_role_name(release_id, role_name)

        if role:
            raise self.http(
                409,
                'Role with name {name} already '
                'exists for release {release}'.format(
                    name=role_name, release=release_id))

        release = self.get_object_or_404(objects.Release, release_id)
        role = self.single.create(release, data)

        raise self.http(201, self.single.to_json(role))

    @pecan.expose(template='json:', content_type='application/json')
    def put(self, release_id, role_name):
        """:http:
            * 200 (OK)
            * 404 (no such object found)
        """
        role = self.get_role_or_404(release_id, role_name)
        data = self.checked_data(instance=role)

        updated = self.single.update(role, data)
        return self.single.to_dict(updated)

    @pecan.expose(template='json:', content_type='application/json')
    def delete(self, release_id, role_name):
        """:http:
            * 204 (object successfully deleted)
            * 400 (cannot delete object)
            * 404 (no such object found)
        """
        role = self.get_role_or_404(release_id, role_name)

        try:
            self.validator.validate_delete(role)
        except errors.CannotDelete as exc:
            raise self.http(400, exc.message)

        self.single.delete(role)
        raise self.http(204)
