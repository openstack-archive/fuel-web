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
from nailgun.api.v1.handlers.base import SingleHandler

from nailgun.api.v1.validators.tag import TagValidator

from nailgun import objects


class TagOwnerHandler(CollectionHandler):

    collection = objects.TagCollection

    @handle_errors
    def GET(self, owner_type, owner_id):
        """:returns: JSONized list of tags.

        :http: * 200 (OK)
        """
        tags = objects.TagCollection.filter_by(
            None,
            owner_type=owner_type,
            owner_id=owner_id
        )
        return self.collection.to_list(tags)


class TagHandler(SingleHandler):
    """Tag single handler"""

    single = objects.Tag
    validator = TagValidator


class TagCollectionHandler(CollectionHandler):
    """Tag collection handler"""

    collection = objects.TagCollection
    validator = TagValidator


class NodeTagAssignmentHandler(BaseHandler):

    @handle_errors
    def POST(self, node_id):
        """Assign tags to node

        :http:
            * 200 (tags successfully assigned)
            * 400 (invalid object data specified)
            * 404 (node instance or tags not found)
        """
        node = self.get_object_or_404(
            objects.Node,
            node_id
        )

        tag_ids = self.get_param_as_set('tags')

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
        """
        node = self.get_object_or_404(
            objects.Node,
            node_id
        )

        tag_ids = self.get_param_as_set('tags')

        tags = self.get_objects_list_or_404(
            objects.TagCollection,
            tag_ids
        )

        objects.Node.unassign_tags(node, tags)
        raise self.http(200, None)
