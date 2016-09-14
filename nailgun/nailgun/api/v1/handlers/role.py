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

import six

from nailgun.api.v1.handlers import base
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import validate
from nailgun.api.v1.validators.role import RoleValidator
from nailgun import errors
from nailgun import objects
from nailgun.objects.serializers.role import RoleSerializer


class RoleHandler(base.SingleHandler):

    validator = RoleValidator

    def _check_role(self, release, role_name):
        if role_name not in release.roles_metadata:
            raise self.http(
                404,
                "Role '{role}' is not found for the release {id}".format(
                    role=role_name, id=release.id))

    @handle_errors
    @validate
    @serialize
    def GET(self, release_id, role_name):
        """Retrieve role

        :http:
            * 200 (OK)
            * 404 (no such object found)
        """
        release = self.get_object_or_404(objects.Release, release_id)
        self._check_role(release, role_name)
        return RoleSerializer.serialize_from_release(release, role_name)

    @handle_errors
    @validate
    @serialize
    def PUT(self, release_id, role_name):
        """Update role

        :http:
            * 200 (OK)
            * 404 (no such object found)
        """
        release = self.get_object_or_404(objects.Release, release_id)
        self._check_role(release, role_name)
        data = self.checked_data(
            self.validator.validate_update, instance=release)
        objects.Release.update_role(release, data)
        return RoleSerializer.serialize_from_release(release, role_name)

    @handle_errors
    def DELETE(self, release_id, role_name):
        """Remove role

        :http:
            * 204 (object successfully deleted)
            * 400 (cannot delete object)
            * 404 (no such object found)
        """
        release = self.get_object_or_404(objects.Release, release_id)
        self._check_role(release, role_name)

        try:
            self.validator.validate_delete(release, role_name)
        except errors.CannotDelete as exc:
            raise self.http(400, exc.message)

        objects.Release.remove_role(release, role_name)
        raise self.http(204)


class RoleCollectionHandler(base.CollectionHandler):

    validator = RoleValidator

    @handle_errors
    @validate
    def POST(self, release_id):
        """Create role for release

        :http:
            * 201 (object successfully created)
            * 400 (invalid object data specified)
            * 409 (object with such parameters already exists)
        """
        release = self.get_object_or_404(objects.Release, release_id)
        try:
            data = self.checked_data(
                self.validator.validate_create, instance=release)
        except errors.AlreadyExists as exc:
            raise self.http(409, exc.message)

        role_name = data['name']
        objects.Release.update_role(release, data)
        raise self.http(
            201, RoleSerializer.serialize_from_release(release, role_name))

    @handle_errors
    @validate
    @serialize
    def GET(self, release_id):
        release = self.get_object_or_404(objects.Release, release_id)
        role_names = six.iterkeys(release.roles_metadata)
        return [RoleSerializer.serialize_from_release(release, name)
                for name in role_names]


class ClusterRolesHandler(base.BaseHandler):

    def _check_role(self, cluster, role_name):
        available_roles = six.iterkeys(objects.Cluster.get_roles(cluster))
        if role_name not in available_roles:
            raise self.http(404, 'Role is not found for the cluster')

    @handle_errors
    @validate
    @serialize
    def GET(self, cluster_id, role_name):
        """:returns: JSON-ed metadata for the role

            :http:
            * 200 (OK)
            * 404 (no such object found)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        self._check_role(cluster, role_name)
        return RoleSerializer.serialize_from_cluster(cluster, role_name)


class ClusterRolesCollectionHandler(base.BaseHandler):

    @handle_errors
    @validate
    @serialize
    def GET(self, cluster_id):
        """:returns: collection of JSON-ed cluster roles metadata

            :http:
            * 200 (OK)
            * 404 (no such object found)
        """
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        roles_names = six.iterkeys(objects.Cluster.get_roles(cluster))
        return [RoleSerializer.serialize_from_cluster(cluster, name)
                for name in roles_names]
