# -*- coding: utf-8 -*-
#    Copyright 2013 Mirantis, Inc.
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
from nailgun.api.v1.validators.json_schema import cluster_schema

from nailgun.errors import errors

from nailgun.objects import ClusterCollection
from nailgun.objects import Release


class ClusterValidator(BasicValidator):

    single_schema = cluster_schema.single_schema
    collection_schema = cluster_schema.collection_schema

    @classmethod
    def _can_update_release(cls, curr_release, pend_release):
        return any([
            # redeploy
            curr_release.id == pend_release.id,

            # update to upper release
            curr_release.operating_system == pend_release.operating_system
            and curr_release.version in pend_release.can_update_from_versions,

            # update to lower release
            curr_release.operating_system == pend_release.operating_system
            and pend_release.version in curr_release.can_update_from_versions,
        ])

    @classmethod
    def _validate_common(cls, data, instance=None):
        d = cls.validate_json(data)

        release_id = d.get("release", d.get("release_id"))
        if release_id:
            if not Release.get_by_uid(release_id):
                raise errors.InvalidData(
                    "Invalid release ID", log_message=True)
        pend_release_id = d.get("pending_release_id")
        if pend_release_id:
            pend_release = Release.get_by_uid(pend_release_id,
                                              fail_if_not_found=True)
            if not release_id:
                if not instance:
                    raise errors.InvalidData(
                        "Cannot set pending release when "
                        "there is no current release",
                        log_message=True
                    )
                release_id = instance.release_id
            curr_release = Release.get_by_uid(release_id)

            if not cls._can_update_release(curr_release, pend_release):
                raise errors.InvalidData(
                    "Cannot set pending release as "
                    "it cannot update current release",
                    log_message=True
                )
        return d

    @classmethod
    def validate(cls, data):
        d = cls._validate_common(data)

        # TODO(ikalnitsky): move it to _validate_common when
        # PATCH method will be implemented
        release_id = d.get("release", d.get("release_id", None))
        if not release_id:
            raise errors.InvalidData(
                u"Release ID is required", log_message=True)

        if "name" in d:
            if ClusterCollection.filter_by(None, name=d["name"]).first():
                raise errors.AlreadyExists(
                    "Environment with this name already exists",
                    log_message=True
                )

        return d

    @classmethod
    def validate_update(cls, data, instance):
        d = cls._validate_common(data, instance=instance)

        if "name" in d:
            query = ClusterCollection.filter_by_not(None, id=instance.id)

            if ClusterCollection.filter_by(query, name=d["name"]).first():
                raise errors.AlreadyExists(
                    "Environment with this name already exists",
                    log_message=True
                )

        for k in ("net_provider",):
            if k in d and getattr(instance, k) != d[k]:
                raise errors.InvalidData(
                    u"Changing '{0}' for environment is prohibited".format(k),
                    log_message=True
                )
        return d


class AttributesValidator(BasicValidator):
    @classmethod
    def validate(cls, data):
        d = cls.validate_json(data)
        if "generated" in d:
            raise errors.InvalidData(
                "It is not allowed to update generated attributes",
                log_message=True
            )
        if "editable" in d and not isinstance(d["editable"], dict):
            raise errors.InvalidData(
                "Editable attributes should be a dictionary",
                log_message=True
            )
        return d
