# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

"""
Handlers dealing with tags
"""

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.handlers.base import validate

from nailgun.api.v1.validators.tag import TagAssignmentValidator
from nailgun.api.v1.validators.tag import TagValidator

from nailgun import consts
from nailgun import errors
from nailgun import objects


class TagMixin(object):

    owner_map = {
        'releases': consts.TAG_OWNER_TYPES.release,
        'clusters': consts.TAG_OWNER_TYPES.cluster,
        'plugins': consts.TAG_OWNER_TYPES.plugin
    }

    owner_cls_map = {
        consts.TAG_OWNER_TYPES.release: objects.Release,
        consts.TAG_OWNER_TYPES.cluster: objects.Cluster,
        consts.TAG_OWNER_TYPES.plugin: objects.Plugin
    }

    def _get_owner_or_404(self, owner_type, owner_id):
        obj_cls = self.owner_cls_map[owner_type]
        return obj_cls, self.get_object_or_404(obj_cls, owner_id)

    def get_data(self, validator, owner_type, owner_id, instance=None):
        owner_cls, owner_obj = self._get_owner_or_404(owner_type,
                                                      owner_id)
        data = self.checked_data(validator,
                                 instance=instance,
                                 owner=owner_obj,
                                 owner_cls=owner_cls)
        data['owner_type'] = owner_type
        data['owner_id'] = owner_id

        return data


class TagOwnerHandler(CollectionHandler, TagMixin):

    validator = TagValidator
    collection = objects.TagCollection

    @handle_errors
    @validate
    @serialize
    def GET(self, owner_type, owner_id):
        """:returns: JSONized list of tags.

        :http:
            * 200 (OK)
            * 404 (owner doesn't exist)
        """
        self._get_owner_or_404(self.owner_map[owner_type], owner_id)

        tags = objects.TagCollection.filter_by(
            None,
            owner_type=self.owner_map[owner_type],
            owner_id=owner_id
        )
        return self.collection.to_list(tags)

    @handle_errors
    def POST(self, owner_type, owner_id):
        """Create tag

        :http:
            * 201 (tag successfully created)
            * 400 (invalid object data specified)
            * 404 (owner doesn't exist)
            * 409 (object already exists)
        """
        data = self.get_data(self.validator.validate_create,
                             self.owner_map[owner_type],
                             owner_id)

        try:
            tag = self.collection.create(data)
        except errors.CannotCreate as exc:
            raise self.http(400, exc.message)

        raise self.http(201, self.collection.single.to_json(tag))


class TagHandler(SingleHandler, TagMixin):
    """Tag single handler"""

    single = objects.Tag
    validator = TagValidator

    @handle_errors
    @validate
    @serialize
    def PUT(self, tag_id):
        """Update tag

        :http:
            * 200 (OK)
            * 400 (invalid object data specified)
            * 404 (no such object found)
        """
        tag = self.get_object_or_404(
            objects.Tag,
            tag_id
        )

        data = self.get_data(self.validator.validate_update,
                             tag.owner_type,
                             tag.owner_id,
                             tag)

        try:
            tag = self.single.update(tag, data)
        except errors.CannotUpdate as exc:
            raise self.http(400, exc.message)

        raise self.http(200, self.single.to_json(tag))


class NodeTagAssignmentHandler(BaseHandler):

    validator = TagAssignmentValidator
    collection = objects.TagCollection

    @handle_errors
    def POST(self, node_id):
        """Assign tags to node

        :http:
            * 200 (tags successfully assigned)
            * 400 (invalid object data specified)
            * 404 (node instance or tags not found)
            * 405 (method not allowed)
        """
        node = self.get_object_or_404(
            objects.Node,
            node_id
        )

        tag_ids = self.checked_data(self.validator.validate_assign,
                                    instance=node)
        tags = self.get_objects_list_or_404(
            objects.TagCollection,
            tag_ids
        )

        objects.Node.assign_tags(node, tags)
        raise self.http(200, None)

    @handle_errors
    def DELETE(self, node_id):
        """Unassign tags from node

        :http:
            * 200 (tags successfully unassigned)
            * 400 (invalid object data specified)
            * 404 (node instance or tags not found)
            * 405 (method not allowed)
        """
        node = self.get_object_or_404(
            objects.Node,
            node_id
        )

        tag_ids = self.checked_data(self.validator.validate_unassign,
                                    instance=node)
        tags = self.get_objects_list_or_404(
            objects.TagCollection,
            tag_ids
        )

        objects.Node.unassign_tags(node, tags)
        raise self.http(204, None)
