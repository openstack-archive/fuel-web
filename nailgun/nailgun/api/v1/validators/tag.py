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

    single_schema = tag.TAG_CREATION_SCHEMA

    @staticmethod
    def _get_assigned_tags(node, tag_ids):
        q_tags = objects.TagCollection.get_node_tags_ids_in_range(node,
                                                                  tag_ids)
        return set(t[0] for t in q_tags)

    @staticmethod
    def _get_cluster_tags_in_range(cluster, tag_ids):
        q_tags = objects.TagCollection.get_cluster_nm_tags_in_range(cluster,
                                                                    tag_ids)
        return set(t[0] for t in q_tags)

    @classmethod
    def _check_volumes(cls, owner_cls, owner_obj, data):
        if data.get('volumes_tags_mapping') is None:
            return
        allowed_ids = set(owner_cls.get_nm_volumes_ids(owner_obj))
        tag_volume_ids = set(v['id'] for v in data['volumes_tags_mapping'])
        missing_volume_ids = tag_volume_ids - allowed_ids

        if missing_volume_ids:
            raise errors.InvalidData(
                "Wrong data in volumes_tags_mapping. Volumes with ids {0}"
                " are not in the list of allowed volumes {1}".format(
                    missing_volume_ids, allowed_ids))

    @classmethod
    def _check_tag_presence(cls, owner_cls, owner_obj, data):
        tags = owner_cls.get_nm_tags(owner_obj, tag=data['tag'])

        if tags:
            raise errors.AlreadyExists("Tag with name '{}' is already present."
                                       "".format(tags[0].tag))

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
                "Tag {} is assigned to nodes '{}'.".format(instance.id,
                                                           ",".join(n_ids))
            )

    @classmethod
    def validate_update(cls, data, instance=None, owner=None, owner_cls=None):
        parsed = cls.validate(data, instance=instance)
        if instance.read_only:
            raise errors.CannotUpdate(
                "Read-only tag '{}' cannot be updated.".format(instance.tag)
            )
        cls._check_tag_presence(owner_cls, owner, parsed)
        cls._check_volumes(owner_cls, owner, parsed)
        return parsed

    @classmethod
    def validate_create(cls, data, instance=None, owner=None, owner_cls=None):
        parsed = cls.validate(data, instance=instance)
        cls._check_tag_presence(owner_cls, owner, parsed)
        cls._check_volumes(owner_cls, owner, parsed)
        return parsed

    @classmethod
    def validate_assignment(cls, data, instance):
        """Validates tags assignment.

        :param data: Json string with tag ids
        :type data: string
        :param instance: A node instance
        :type node: nailgun.db.sqlalchemy.models.node.Node
        """
        tag_ids = set(super(TagValidator, cls).validate(data))

        if not instance.cluster:
            raise errors.NotAllowed("Node '{}' is not in a cluster."
                                    "".format(instance.id))
        for t in tag_ids:
            if not isinstance(t, int):
                raise errors.InvalidData(
                    "Tag '{}' can not be assigned to the node '{}' as only "
                    "a numeric notation is supported.".format(t, instance.id)
                )

        foreign_tags = (tag_ids -
                        cls._get_cluster_tags_in_range(instance.cluster,
                                                       tag_ids))

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
        :type node: nailgun.db.sqlalchemy.models.node.Node
        """
        tag_ids = cls.validate_assignment(data, instance)
        assigned_tags = tag_ids & cls._get_assigned_tags(instance, tag_ids)
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
        :type node: nailgun.db.sqlalchemy.models.node.Node
        """
        tag_ids = cls.validate_assignment(data, instance)
        not_assigned_tags = (tag_ids -
                             cls._get_assigned_tags(instance, tag_ids))
        if not_assigned_tags:
            raise errors.InvalidData("Tags '{}' are not assigned to the node "
                                     "{}.".format(not_assigned_tags,
                                                  instance.id))
        return tag_ids

    @classmethod
    def validate(cls, data, instance=None):
        parsed = super(TagValidator, cls).validate(data)
        cls.validate_schema(parsed, cls.single_schema)
        return parsed
