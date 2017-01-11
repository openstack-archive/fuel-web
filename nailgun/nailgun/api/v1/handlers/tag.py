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
from nailgun.api.v1.validators.tag import TagValidator
from nailgun import errors
from nailgun import objects
from nailgun.objects.serializers.tag import TagSerializer


class TagMixIn(object):

    def _get_object_or_404(self, obj_type, obj_id):
        obj_cls = {
            'releases': objects.Release,
            'clusters': objects.Cluster,
        }[obj_type]
        return obj_cls, self.get_object_or_404(obj_cls, obj_id)


class TagHandler(base.SingleHandler, TagMixIn):

    validator = TagValidator

    def _check_tag(self, obj_cls, obj, tag_name):
        if tag_name not in obj_cls.get_own_tags(obj):
            raise self.http(
                404,
                "Tag '{}' is not found for the {} {}".format(
                    tag_name, obj_cls.__name__.lower(), obj.id))

    @handle_errors
    @validate
    @serialize
    def GET(self, obj_type, obj_id, tag_name):
        """Retrieve tag

        :http:
            * 200 (OK)
            * 404 (no such object found)
        """
        obj_cls, obj = self._get_object_or_404(obj_type, obj_id)
        self._check_tag(obj_cls, obj, tag_name)
        return TagSerializer.serialize_from_obj(obj_cls, obj, tag_name)

    @handle_errors
    @validate
    @serialize
    def PUT(self, obj_type, obj_id, tag_name):
        """Update tag

        :http:
            * 200 (OK)
            * 400 (wrong data specified)
            * 404 (no such object found)
        """
        obj_cls, obj = self._get_object_or_404(obj_type, obj_id)
        self._check_tag(obj_cls, obj, tag_name)
        data = self.checked_data(
            self.validator.validate_update, instance_cls=obj_cls, instance=obj)
        obj_cls.update_tag(obj, data)
        return TagSerializer.serialize_from_obj(obj_cls, obj, tag_name)

    @handle_errors
    def DELETE(self, obj_type, obj_id, tag_name):
        """Remove tag

        :http:
            * 204 (object successfully deleted)
            * 400 (cannot delete object)
            * 404 (no such object found)
        """
        obj_cls, obj = self._get_object_or_404(obj_type, obj_id)
        self._check_tag(obj_cls, obj, tag_name)
        obj_cls.remove_tag(obj, tag_name)
        raise self.http(204)


class TagCollectionHandler(base.CollectionHandler, TagMixIn):

    validator = TagValidator

    @handle_errors
    @validate
    def POST(self, obj_type, obj_id):
        """Create tag for release or cluster

        :http:
            * 201 (object successfully created)
            * 400 (invalid object data specified)
            * 409 (object with such parameters already exists)
            * 404 (no such object found)
        """
        obj_cls, obj = self._get_object_or_404(obj_type, obj_id)
        try:
            data = self.checked_data(
                self.validator.validate_create,
                instance_cls=obj_cls,
                instance=obj)
        except errors.AlreadyExists as exc:
            raise self.http(409, exc.message)

        tag_name = data['name']
        obj_cls.update_tag(obj, data)
        raise self.http(
            201, TagSerializer.serialize_from_obj(obj_cls, obj, tag_name))

    @handle_errors
    @validate
    @serialize
    def GET(self, obj_type, obj_id):
        """Retrieve tag list of release or cluster

        :http:
            * 200 (OK)
            * 404 (no such object found)
        """
        obj_cls, obj = self._get_object_or_404(obj_type, obj_id)
        tag_names = six.iterkeys(obj_cls.get_tags_metadata(obj))
        return [TagSerializer.serialize_from_obj(obj_cls, obj, tag_name)
                for tag_name in tag_names]
