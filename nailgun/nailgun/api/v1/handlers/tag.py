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

from nailgun.api.v1.validators.tag import TagValidator


from nailgun import errors
from nailgun import objects


class TagOwnerHandler(CollectionHandler):

    validator = TagValidator
    collection = objects.TagCollection
    owner_map = {
        'releases': 'release',
        'clusters': 'cluster',
        'plugins': 'plugin'
    }

    def _get_owner_or_404(self, owner_type, owner_id):
        obj_cls = {
            'releases': objects.Release,
            'clusters': objects.Cluster,
            'plugins': objects.Plugin
        }[owner_type]
        return self.get_object_or_404(obj_cls, owner_id)

    @handle_errors
    @validate
    @serialize
    def GET(self, owner_type, owner_id):
        """:returns: JSONized list of tags.

        :http:
            * 200 (OK)
            * 404 (owner doesn't exist)
        """
        self._get_owner_or_404(owner_type, owner_id)

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
        """
        owner_obj = self._get_owner_or_404(owner_type, owner_id)
        data = self.checked_data(self.validator.validate_create,
                                 instance=owner_obj)
        data.pop('id', None)
        data['owner_type'] = self.owner_map[owner_type]
        data['owner_id'] = owner_id

        try:
            tag = self.collection.create(data)
        except errors.CannotCreate as exc:
            raise self.http(400, exc.message)

        raise self.http(201, self.collection.single.to_json(tag))


class TagHandler(SingleHandler):
    """Tag single handler"""

    single = objects.Tag
    validator = TagValidator


class NodeTagAssignmentHandler(BaseHandler):

    validator = TagValidator

    @staticmethod
    def _get_assigned_tags(node, tag_ids):
        q_tags = objects.TagCollection.get_node_tags_ids_in_range(node,
                                                                  tag_ids)
        return set([t[0] for t in q_tags])

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

        assigned_tags = (set(tag_ids) &
                         self._get_assigned_tags(node, tag_ids))
        if assigned_tags:
            raise self.http(405, "Tags '{}' are already assigned to the "
                                 "node {}.".format(assigned_tags, node_id))

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

        tag_ids = self.checked_data(self.validator.validate_assign,
                                    instance=node)

        tags = self.get_objects_list_or_404(
            objects.TagCollection,
            tag_ids
        )

        not_assigned_tags = (set(tag_ids) -
                             self._get_assigned_tags(node, tag_ids))
        if not_assigned_tags:
            raise self.http(405, "Tags '{}' are not assigned to the node "
                                 "{}.".format(not_assigned_tags, node_id))

        objects.Node.unassign_tags(node, tags)
        raise self.http(204, None)
