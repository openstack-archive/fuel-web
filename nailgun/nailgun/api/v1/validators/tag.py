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

    @classmethod
    def _check_volumes(cls, data):
        if data.get('volumes_tags_mapping') is None:
            return
        #  owner_cls, owner_obj = objects.Tag.get_owner(data['owner_type'],
        #                                               data['owner_id'])
        #  allowed_ids = set(v['id']
        #                    for v in owner_cls.get_tags_volumes(owner_obj))
        #  tag_volume_ids = set(v['id'] for v in data['volumes_tags_mapping'])
        #  missing_volume_ids = tag_volume_ids - allowed_ids

        #  if missing_volume_ids:
        #      raise errors.InvalidData(
        #          "Wrong data in volumes_tags_mapping. Volumes with ids {0}"
        #          " are not in the list of allowed volumes {1}".format(
        #              missing_volume_ids, allowed_ids))

    @classmethod
    def validate_delete(cls, data, instance):
        if instance.read_only:
            raise errors.CannotDelete(
                "Read-only tags cannot be deleted."
            )

        n_ids = [str(n.id)
                 for n in objects.TagCollection.get_tag_nodes(instance)]

        if n_ids:
            raise errors.CannotDelete(
                "Tag {} is assigned to nodes '{}'.".format(instance.id,
                                                           ",".join(n_ids))
            )

    @classmethod
    def validate_update(cls, data, instance):
        parsed = cls.validate(data, instance=instance)
        if instance.read_only:
            raise errors.CannotUpdate(
                "Read-only tags cannot be updated."
            )
        return parsed

    @classmethod
    def validate_create(cls, data, instance):
        parsed = cls.validate(data, instance=instance)
        return parsed

    @classmethod
    def validate_assign(cls, data, instance):
        if not instance.cluster:
            raise errors.NotAllowed("Node '{}' is not in a cluster."
                                    "".format(instance.id))
        parsed = super(TagValidator, cls).validate(data)

        for t in parsed:
            if not isinstance(t, int):
                raise errors.InvalidData(
                    "Tag's assignment supports only numeric notation."
                )
        return parsed

    @classmethod
    def validate(cls, data, instance=None):
        parsed = super(TagValidator, cls).validate(data)
        cls.validate_schema(parsed, cls.single_schema)
        return parsed
