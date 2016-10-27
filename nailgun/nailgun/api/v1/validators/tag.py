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

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import tag

from nailgun import errors
from nailgun import objects


class TagValidator(BasicValidator):

    single_schema = tag.TAG_SCHEMA

    @classmethod
    def validate_delete(cls, data, instance):
        if instance.read_only:
            raise errors.CannotDelete(
                "Read-only tag '{}' cannot be deleted.".format(instance.tag)
            )

        n_ids = [str(n)
                 for n in objects.TagCollection.get_tag_nodes_ids(instance)]

        if n_ids:
            raise errors.CannotDelete(
                "Tag {} is assigned to nodes '{}'. You should unassign tag "
                "from these nodes before remove it. ".format(instance.tag,
                                                             ",".join(n_ids))
            )

    @classmethod
    def validate_update(cls, data, instance=None, owner=None, owner_cls=None):
        parsed = cls.validate(data, instance=instance)
        if instance.read_only:
            raise errors.CannotUpdate(
                "Read-only tag '{}' cannot be updated.".format(instance.tag)
            )
        tags = owner_cls.get_nm_tags(owner, tag=parsed['tag'])
        if tags and tags[0].id != instance.id:
            raise errors.AlreadyExists("Tag can not be renamed to '{}'."
                                       "Tag with this name is already present."
                                       "".format(tags[0].tag))
        return parsed

    @classmethod
    def validate_create(cls, data, instance=None, owner=None, owner_cls=None):
        parsed = cls.validate(data, instance=instance)
        tags = owner_cls.get_nm_tags(owner, tag=parsed['tag'])
        if tags:
            raise errors.AlreadyExists("Tag with name '{}' is already present."
                                       "".format(tags[0].tag))
        return parsed

    @classmethod
    def validate(cls, data, instance=None):
        parsed = super(TagValidator, cls).validate(data)
        cls.validate_schema(parsed, cls.single_schema)
        return parsed


class TagAssignmentValidator(BasicValidator):

    @classmethod
    def validate_assignment(cls, data, instance):
        """Validates tags assignment.

        :param data: Json string with tag ids
        :type data: string
        :param instance: A node instance
        :type instance: models.Node
        """
        tag_ids = set(cls.validate_ids_list(cls.validate(data)))

        if not instance.cluster:
            raise errors.NotAllowed("Node '{}' is not in a cluster."
                                    "".format(instance.id))

        if instance.cluster.is_locked:
            raise errors.NotAllowed("Tag assignment is not allowed for node "
                                    "'{}' as it belongs to cluster '{}' where "
                                    "deployment is in progress.".format(
                                        instance.id, instance.cluster.id))

        cluster_tags = objects.TagCollection.get_cluster_tags_in_range(
            instance.cluster, tag_ids)

        foreign_tags = tag_ids - cluster_tags

        if foreign_tags:
            raise errors.InvalidData("Tags '{}' are not present in node '{}' "
                                     "namespace.".format(foreign_tags,
                                                         instance.id))
        return tag_ids

    @classmethod
    def validate_assign(cls, data, instance):
        """Validates tags assignment.

        :param data: Json string with tag ids
        :type data: string
        :param instance: A node instance
        :type instance: models.Node
        """
        tag_ids = cls.validate_assignment(data, instance)

        node_tags = objects.TagCollection.get_assigned_tags(instance, tag_ids)
        assigned_tags = tag_ids & node_tags
        if assigned_tags:
            raise errors.InvalidData("Tags '{}' are already assigned to the "
                                     "node {}.".format(assigned_tags,
                                                       instance.id))
        return tag_ids

    @classmethod
    def validate_unassign(cls, data, instance):
        """Validates tags unassignment.

        :param data: Json string with tag ids
        :type data: string
        :param instance: A node instance
        :type instance: models.Node
        """
        tag_ids = cls.validate_assignment(data, instance)

        assigned_tags = objects.TagCollection.get_assigned_tags(instance,
                                                                tag_ids)
        not_assigned_tags = tag_ids - assigned_tags

        if not_assigned_tags:
            raise errors.InvalidData("Tags '{}' are not assigned to the node "
                                     "{}.".format(not_assigned_tags,
                                                  instance.id))
        return tag_ids
