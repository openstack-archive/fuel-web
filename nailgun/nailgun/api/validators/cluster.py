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

from nailgun.api.validators.base import BasicValidator
from nailgun.errors import errors

from nailgun.objects import ClusterCollection
from nailgun.objects import Release


class ClusterValidator(BasicValidator):
    @classmethod
    def _validate_common(cls, data, instance=None):
        d = cls.validate_json(data)
        if d.get("name"):
            if ClusterCollection.filter_by(
                None,
                name=d["name"]
            ).first():
                raise errors.AlreadyExists(
                    "Environment with this name already exists",
                    log_message=True
                )
        release_id = d.get("release", d.get("release_id", None))
        if release_id:
            if not Release.get_by_uid(release_id):
                raise errors.InvalidData(
                    "Invalid release ID",
                    log_message=True
                )
        if d.get("pending_release_id", None):
            pend_rel = Release.get_by_uid(d["pending_release_id"])
            if not pend_rel:
                raise errors.InvalidData(
                    "Invalid pending release ID",
                    log_message=True
                )
            if not release_id and not instance:
                raise errors.InvalidData(
                    "Cannot set pending release when "
                    "there is no current release",
                    log_message=True
                )
            curr_rel = Release.get_by_uid(release_id)
            if release_id != d["pending_release_id"] and (
                    curr_rel.operating_system != pend_rel.operating_system or
                    curr_rel.openstack_version not in
                    pend_rel.can_update_openstack_versions):
                raise errors.InvalidData(
                    "Cannot set pending release as "
                    "it cannot update current release",
                    log_message=True
                )
        return d

    @classmethod
    def validate(cls, data):
        d = cls._validate_common(data)
        release_id = d.get("release", d.get("release_id", None))
        if not release_id:
            raise errors.InvalidData(
                u"Release ID is required",
                log_message=True
            )
        return d

    @classmethod
    def validate_update(cls, data, instance):
        d = cls._validate_common(data, instance)
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

    @classmethod
    def validate_fixture(cls, data):
        """Here we just want to be sure that data is logically valid.
        We try to generate "generated" parameters. If there will not
        be any error during generating then we assume data is
        logically valid.
        """
        d = cls.validate_json(data)
        if "generated" in d:
            cls.traverse(d["generated"])
